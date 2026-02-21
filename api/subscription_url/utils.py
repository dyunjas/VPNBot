import base64
from datetime import datetime, timezone

from fastapi import Response


def _to_unix(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _build_expire_only_header(expire_dt: datetime | None) -> dict[str, str]:
    if not expire_dt:
        return {}
    return {
        "Subscription-Userinfo": f"upload=0; download=0; total=0; expire={_to_unix(expire_dt)}"
    }


def _profile_title(name: str) -> dict[str, str]:
    b64 = base64.b64encode(name.encode("utf-8")).decode("ascii")
    return {"profile-title": f"base64:{b64}"}


def _profile_update_interval(hours: int = 6) -> dict[str, str]:
    return {"profile-update-interval": str(hours)}


def _profile_web_page(url: str) -> dict[str, str]:
    return {"profile-web-page-url": url}


def _b64_response(lines: list[str], headers: dict[str, str] | None = None) -> Response:
    plain = "\n".join(lines)
    b64 = base64.b64encode(plain.encode("utf-8")).decode("ascii")
    return Response(content=b64, media_type="text/plain; charset=utf-8", headers=headers or {})


def expired_subscription_response(headers: dict[str, str] | None = None) -> Response:
    fake_uris = [
        (
            "vless://00000000-0000-0000-0000-000000000001@expired1:443"
            "?type=tcp&encryption=none"
            "#🔴 Подписка не найдена"
        ),
        (
            "vless://00000000-0000-0000-0000-000000000002@expired2:443"
            "?type=tcp&encryption=none"
            "#⚠️ Продлите подписку"
        ),
        (
            "vless://00000000-0000-0000-0000-000000000003@expired3:443"
            "?type=tcp&encryption=none"
            "#🌙 t.me/LunetVpnBot"
        ),
    ]
    return _b64_response(fake_uris, headers=headers)


def device_limit_response(headers: dict[str, str] | None = None) -> Response:
    fake_uris = [
        (
            "vless://00000000-0000-0000-0000-000000000011@limit1:443"
            "?type=tcp&encryption=none"
            "#🚫 Лимит устройств исчерпан"
        ),
        (
            "vless://00000000-0000-0000-0000-000000000012@limit2:443"
            "?type=tcp&encryption=none"
            "#🧹 Удалите устройство в боте"
        ),
        (
            "vless://00000000-0000-0000-0000-000000000013@limit3:443"
            "?type=tcp&encryption=none"
            "#🌙 t.me/LunetVpnBot"
        ),
    ]
    return _b64_response(fake_uris, headers=headers)
