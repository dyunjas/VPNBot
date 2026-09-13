from __future__ import annotations

from html import escape


def render_code_email(code: str, purpose: str = "login") -> tuple[str, str]:
    """Return an accessible HTML and plain-text one-time-code email."""
    normalized_purpose = (purpose or "login").strip().lower()
    is_bind = normalized_purpose == "bind"
    is_admin = normalized_purpose == "admin_login"
    title = "Код подтверждения" if is_admin else ("Подтверждение email" if is_bind else "Код входа")
    heading = "Подтвердите вход" if is_admin else ("Подтвердите адрес электронной почты" if is_bind else "Вход в личный кабинет")
    description = "Введите этот код в форме подтверждения." if is_admin else ("Используйте этот код, чтобы привязать email к аккаунту Lunet." if is_bind else "Используйте этот код, чтобы войти в личный кабинет Lunet.")
    expiry = "Код действует 10 минут."
    safety = "Если вы не запрашивали код, просто проигнорируйте это письмо."
    plain = f"{title}: {code}\n\n{heading}\n{description}\n\n{expiry} {safety}"
    safe_code = escape(str(code))
    safe_title = escape(title)
    safe_heading = escape(heading)
    safe_description = escape(description)
    html = f"""<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"></head>
<body style="margin:0;background:#fafafa;color:#18181b;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fafafa;padding:32px 14px;"><tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border:1px solid #e4e4e7;border-radius:14px;box-shadow:0 12px 30px rgba(24,24,27,.06);">
      <tr><td style="padding:22px 24px 0;"><div style="font-size:18px;font-weight:750;letter-spacing:-.03em;">Lunet</div></td></tr>
      <tr><td style="padding:26px 24px 8px;"><div style="color:#71717a;font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;">{safe_title}</div><h1 style="margin:10px 0 0;font-size:28px;line-height:1.12;letter-spacing:-.04em;">{safe_heading}</h1><p style="margin:13px 0 0;color:#71717a;font-size:14px;line-height:1.6;">{safe_description}</p></td></tr>
      <tr><td style="padding:20px 24px 0;"><div style="padding:22px 16px;border:1px solid #e4e4e7;border-radius:10px;background:#f4f4f5;text-align:center;"><div style="margin-bottom:10px;color:#71717a;font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;">Код подтверждения</div><div style="color:#18181b;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:38px;font-weight:800;letter-spacing:.22em;padding-left:.22em;">{safe_code}</div></div></td></tr>
      <tr><td style="padding:18px 24px 0;"><div style="padding:13px 14px;border:1px solid #e4e4e7;border-radius:8px;color:#71717a;font-size:12px;line-height:1.55;">{expiry}<br>{safety}</div></td></tr>
      <tr><td style="padding:24px;"><div style="border-top:1px solid #e4e4e7;padding-top:15px;color:#a1a1aa;font-size:11px;line-height:1.5;text-align:center;">© Lunet 2026<br>Это письмо отправлено автоматически.</div></td></tr>
    </table>
  </td></tr></table>
</body>
</html>"""
    return html, plain
