import base64
from datetime import datetime, timezone

from fastapi import Response

_BOT_REF = "t.me/LunetVpnBot"
_PLACEHOLDER_UUID_PREFIX = "00000000-0000-0000-0000-0000000000"


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


def _placeholder_vless_lines(prefix: str, messages: list[str]) -> list[str]:
    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        host = f"{prefix}{index}"
        suffix = f"{index:02d}"
        lines.append(
            f"vless://{_PLACEHOLDER_UUID_PREFIX}{suffix}@{host}:443"
            f"?type=tcp&encryption=none#{message}"
        )
    return lines


def expired_subscription_response(headers: dict[str, str] | None = None) -> Response:
    fake_uris = _placeholder_vless_lines(
        "expired",
        [
            "🔴 Подписка не найдена",
            "⚠️ Продлите подписку",
            f"🌙 {_BOT_REF}",
        ],
    )
    return _b64_response(fake_uris, headers=headers)


def traffic_limit_response(headers: dict[str, str] | None = None) -> Response:
    fake_uris = _placeholder_vless_lines(
        "traffic",
        [
            "📉 Гигабайты закончились",
            "🛒 Докупите гигабайты в боте",
            f"🌙 {_BOT_REF}",
        ],
    )
    return _b64_response(fake_uris, headers=headers)


def unsupported_app_response(headers: dict[str, str] | None = None) -> Response:
    fake_uris = _placeholder_vless_lines(
        "unsupported",
        [
            "⚠️ Приложение не поддерживается",
            "💬 Обратитесь в поддержку",
            f"🌙 {_BOT_REF}",
        ],
    )
    return _b64_response(fake_uris, headers=headers)
