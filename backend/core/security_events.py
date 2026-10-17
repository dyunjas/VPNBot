"""Alert on denied sensitive requests, never on ordinary authenticated traffic."""
import logging
import re
from urllib.parse import unquote

log = logging.getLogger("vpn.security")
PROBES = ("/.env", "/.git", "/wp-admin", "/wp-login", "/phpmyadmin", "/actuator", "/debug", "/server-status", "/vendor/phpunit")
DENIED = {400,401,403,404,405,413,422,429}


def observe_security_response(request, status: int):
    if status not in DENIED or request.method == "OPTIONS": return
    if getattr(request.state,"is_api_proxy",False): return
    identity = getattr(request.state,"admin_auth",None) or {}
    if identity.get("_reauthentication_required"): return
    path = unquote(request.url.path).lower()
    if path == "/api/admin/auth/me" and request.method in {"GET","HEAD"} and status==401: return
    if path.startswith(PROBES):
        kind = "scan"
        # No attacker-controlled suffix in reports or fingerprints.
        target = next(prefix for prefix in PROBES if path.startswith(prefix))
    elif path == "/api/admin" or path.startswith("/api/admin/"):
        kind = "admin_login" if path.startswith("/api/admin/auth/") else "admin_access"
        target = getattr(request.scope.get("route"),"path","/api/admin/{unknown}")
    elif path.startswith(("/api/users/","/api/bot/")):
        kind, target = "internal_api", getattr(request.scope.get("route"),"path","/api/users/{unknown}")
    elif path == "/remnawave-webhook" or (path.startswith("/api/payments/") and path.endswith("webhook")):
        kind, target = "webhook", path
    else: return
    target = re.sub(r"[\r\n\x00-\x1f]","",target.split("?",1)[0])[:180]
    target = re.sub(r"/[0-9a-f-]{32,}(?=/|$)|/\d+(?=/|$)","/{id}",target,flags=re.I)
    peer = request.client.host if request.client else "unknown"
    # The ASGI server resolves trusted proxy addresses. Do not trust raw X-Forwarded-For.
    log.warning("[security] %s %s %s HTTP %s",kind,request.method,target,status,
                extra={"security_event":True,"security_peer":peer,"app_context":"API Security"})
