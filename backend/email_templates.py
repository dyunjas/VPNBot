from __future__ import annotations

from datetime import datetime
from html import escape


def render_email_frame(*, heading: str, content_html: str, eyebrow: str = "") -> str:
    """Wrap trusted, escaped content in the shared Lunet table layout."""
    label = f'<p style="margin:0 0 14px;color:#0184f8;font-size:12px;letter-spacing:1px;">{escape(eyebrow)}</p>' if eyebrow else ""
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"></head>
<body style="margin:0;background:#f4f4f5;color:#18181b;font-family:Arial,'Segoe UI',sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;"><tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
<tr><td align="center" style="padding:0 0 20px;font-size:24px;font-weight:700;letter-spacing:-.6px;">Lunet <span style="font-size:11px;font-weight:400;color:#71717a;letter-spacing:1px;">VPS</span></td></tr>
<tr><td style="padding:32px 28px 24px;background:#fff;border:1px solid #e4e4e7;border-bottom:0;border-radius:26px 26px 0 0;">{label}<h1 style="margin:0;color:#18181b;font-size:30px;font-weight:600;line-height:1.2;letter-spacing:-.6px;overflow-wrap:anywhere;">{escape(heading)}</h1><div style="width:44px;height:3px;margin-top:20px;background:#0184f8;border-radius:3px;"></div></td></tr>
<tr><td style="padding:28px;background:#fff;border-left:1px solid #e4e4e7;border-right:1px solid #e4e4e7;">{content_html}</td></tr>
<tr><td align="center" style="padding:22px 24px;background:#000;border-radius:0 0 26px 26px;color:#a1a1aa;font-size:11px;line-height:1.6;">© Lunet · {datetime.now().year}<br>Это письмо отправлено автоматически.</td></tr>
</table></td></tr></table></body></html>"""


def render_code_email(code: str, purpose: str = "login", *, ttl_seconds: int = 600) -> tuple[str, str]:
    """Render the same code and actual expiry in HTML and plain text."""
    purpose = (purpose or "login").strip().lower()
    is_bind = purpose == "bind"
    is_admin = purpose == "admin_login"
    heading = "Подтвердите адрес электронной почты" if is_bind else "Код подтверждения для входа"
    request = "подтверждение email" if is_bind else ("вход в панель управления" if is_admin else "вход в личный кабинет")
    minutes = max(1, (int(ttl_seconds) + 59) // 60)
    expiry = f"{minutes} мин."
    safety = "Если вы не запрашивали этот код, просто проигнорируйте письмо. Никому не передавайте код подтверждения."
    content = f"""<p style="margin:0 0 14px;color:#71717a;font-size:13px;line-height:1.6;">Ваш одноразовый код</p>
<div style="padding:22px 10px;border:1px solid #d6eaff;border-radius:18px;background:#f0f7ff;color:#0184f8;text-align:center;font-size:32px;font-weight:700;letter-spacing:6px;font-family:Arial,sans-serif;overflow-wrap:anywhere;">{escape(str(code))}</div>
<div style="margin-top:20px;padding:16px;border-left:3px solid #0184f8;border-radius:0 14px 14px 0;background:#f4f4f5;color:#71717a;font-size:12px;line-height:1.8;">Срок действия: <strong style="color:#18181b;">{expiry}</strong><br>Запрос: <strong style="color:#18181b;">{escape(request)}</strong></div>
<p style="margin:24px 0 0;color:#71717a;font-size:13px;line-height:1.7;">{safety}</p>"""
    plain = f"{heading}\n\nВаш одноразовый код: {code}\nСрок действия: {expiry}\nЗапрос: {request}\n\n{safety}"
    return render_email_frame(heading=heading, content_html=content), plain
