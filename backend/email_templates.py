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
<body style="margin:0;padding:0;background:#5b7cfa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#182338;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:
    radial-gradient(circle at top left, rgba(255,255,255,0.28), transparent 28%),
    linear-gradient(180deg, #6a86ff 0%, #5b7cfa 100%);
    padding:32px 14px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="max-width:620px;width:100%;">
          <tr>
            <td>
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.28);border-radius:28px;padding:16px;">
                <tr>
                  <td>
                    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#ffffff;border:1px solid #dbe6ff;border-radius:24px;box-shadow:0 24px 48px rgba(36,54,120,0.18);overflow:hidden;">
                      <tr>
                        <td style="padding:18px 22px 0;">
                          <div style="display:inline-block;background:linear-gradient(180deg,#6b86ff 0%,#4c6fff 100%);color:#ffffff;font-size:13px;line-height:1;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;border-radius:999px;padding:12px 14px;">
                            Lunet
                          </div>
                        </td>
                      </tr>

                      <tr>
                        <td style="padding:18px 22px 10px;">
                          <div style="font-size:12px;line-height:1.2;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;color:#4c6fff;margin:0 0 12px;">
                            {escape(title)}
                          </div>
                          <h1 style="margin:0;font-size:30px;line-height:1.08;font-weight:800;letter-spacing:-0.03em;color:#182338;">
                            {escape(heading)}
                          </h1>
                          <p style="margin:14px 0 0;font-size:16px;line-height:1.65;color:#5f6f8b;max-width:430px;">
                            {escape(description)}
                          </p>
                        </td>
                      </tr>

                      <tr>
                        <td style="padding:16px 22px 0;">
                          <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:
                            linear-gradient(135deg, rgba(76,111,255,0.10), rgba(255,255,255,0) 55%),
                            linear-gradient(180deg, #fdfefe 0%, #f5f8ff 100%);
                            border:1px solid #d7e3ff;border-radius:22px;">
                            <tr>
                              <td align="center" style="padding:18px 16px 8px;">
                                <div style="font-size:11px;line-height:1.2;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;color:#7e8daa;margin:0 0 10px;">
                                  Код подтверждения
                                </div>
                                <div style="font-size:42px;line-height:1;font-weight:800;letter-spacing:0.32em;color:#182338;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace;padding-left:0.32em;">
                                  {escape(code)}
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td align="center" style="padding:0 16px 18px;">
                                <div style="display:inline-block;background:#ffffff;border:1px solid #d7e3ff;border-radius:999px;padding:10px 14px;font-size:13px;line-height:1.2;font-weight:700;color:#4c5d7b;">
                                  Код действует 10 минут
                                </div>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>

                      <tr>
                        <td style="padding:18px 22px 0;">
                          <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f8fbff;border:1px solid #e2ebff;border-radius:18px;">
                            <tr>
                              <td style="padding:14px 16px;font-size:14px;line-height:1.6;color:#61728f;">
                                Если вы не запрашивали этот код, просто проигнорируйте письмо. Доступ без подтверждения не будет предоставлен.
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>

                      <tr>
                        <td style="padding:22px 22px 22px;">
                          <div style="border-top:1px solid #e9effb;padding-top:16px;font-size:12px;line-height:1.7;color:#7e8daa;text-align:center;">
                            © Lunet 2026<br>
                            Вход и подтверждение действий в кабинете
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
      </td>
    </tr>
  </table>
</body>
</html>"""

    return html, plain
