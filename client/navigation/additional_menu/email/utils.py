import secrets
import ssl
import smtplib
from email.message import EmailMessage

from server.core.config import settings


def generate_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def _build_message(to_email: str, code: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"LunetPN <{settings.SMTP_NOREPLY_USER}>"
    msg["To"] = to_email
    msg["Subject"] = "Код подтверждения"
    msg.set_content(
        f"Ваш код подтверждения: {code}\n\n"
        f"Код действует 10 минут.\n"
        f"Если вы не запрашивали код — просто проигнорируйте письмо."
    )
    return msg


def send_email_code(to_email: str, code: str) -> None:
    msg = _build_message(to_email, code)
    ctx = ssl.create_default_context()

    try:
        with smtplib.SMTP(settings.SMTP_HOST, 2525, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(settings.SMTP_NOREPLY_USER, settings.SMTP_NOREPLY_PASS)
            server.send_message(msg)
            return
    except Exception:
        pass

    with smtplib.SMTP_SSL(settings.SMTP_HOST, 465, context=ctx, timeout=20) as server:
        server.login(settings.SMTP_NOREPLY_USER, settings.SMTP_NOREPLY_PASS)
        server.send_message(msg)