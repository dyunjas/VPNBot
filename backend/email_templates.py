from __future__ import annotations

from html import escape


def render_code_email(code: str, purpose: str = "login") -> tuple[str, str]:
    """
    Returns (html_body, plain_body) for OTP code emails.
    purpose: "login" | "bind"
    """
    purpose = (purpose or "login").strip().lower()

    if purpose == "bind":
        title = "Код подтверждения"
        heading = "Подтверждение email"
        description = "Используйте этот код для привязки email к аккаунту Lunet."
        footer = "Код действует 10 минут.\nЕсли вы не запрашивали код, проигнорируйте это письмо."
    else:
        title = "Код входа"
        heading = "Вход в кабинет"
        description = "Используйте этот код для входа в личный кабинет Lunet."
        footer = "Код действует 10 минут.\nЕсли вы не запрашивали код, проигнорируйте это письмо."

    plain = f"{title}: {code}\n\n{heading}\n{description}\n\n{footer}"

    html = f"""\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light only">
</head>
<body style="margin:0;padding:0;background:#eef3f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#152130;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#eef3f9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="max-width:560px;width:100%;background:#f7f9fc;border:1px solid #e4ebf4;border-radius:18px;padding:34px 18px;">
          <tr>
            <td align="center">
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="max-width:470px;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;box-shadow:0 10px 24px rgba(15,30,55,0.06);">
                <tr>
                  <td align="center" style="padding:36px 28px 18px;">
                    <div style="font-size:28px;line-height:1;font-weight:800;letter-spacing:-0.03em;color:#2f6fed;margin:0 0 24px;">Lunet</div>
                    <h1 style="margin:0;font-size:24px;line-height:1.25;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">{escape(heading)}</h1>
                    <p style="margin:12px 0 0;font-size:16px;line-height:1.55;color:#8a95a6;max-width:360px;">{escape(description)}</p>
                  </td>
                </tr>

                <tr>
                  <td style="padding:6px 28px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                      <tr>
                        <td align="center" style="background:#eef4ff;border:1px solid #dce6ff;border-radius:14px;padding:18px 16px;">
                          <div style="font-size:40px;line-height:1;font-weight:800;letter-spacing:0.3em;color:#111827;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace;">
                            {escape(code)}
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <tr>
                  <td align="center" style="padding:24px 28px 0;">
                    <p style="margin:0;font-size:15px;line-height:1.55;color:#a3acb9;">
                      Код действует 10 минут.<br>
                      Если вы не запрашивали код, проигнорируйте это письмо.
                    </p>
                  </td>
                </tr>

                <tr>
                  <td style="padding:22px 28px 28px;">
                    <div style="border-top:1px solid #edf2f7;padding-top:18px;text-align:center;font-size:12px;line-height:1.5;color:#c0c7d1;">
                      &copy; Lunet &middot; VPN сервис
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return html, plain
