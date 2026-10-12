from __future__ import annotations

import asyncio
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.email_templates import render_email_frame
from backend.core.config import settings
from backend.core.logger_config import logger
from backend.database.models import UserActivity
from backend.services.activity_service import ActivityService


CABINET_URL = (os.getenv("CABINET_PUBLIC_URL") or "https://app.lunet.pro/cabinet").strip()


def _format_date(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def _render_email(
    *,
    eyebrow: str,
    heading: str,
    description: str,
    rows: list[tuple[str, str]],
    note: str,
) -> tuple[str, str]:
    safe_rows = [(escape(str(label)), escape(str(value))) for label, value in rows]
    rows_html = "".join(
        f'<tr><td style="padding:13px 0;color:#71717a;font-size:13px;border-bottom:1px solid #f1f1f2;">{label}</td>'
        f'<td align="right" style="padding:13px 0;color:#18181b;font-size:13px;font-weight:700;border-bottom:1px solid #f1f1f2;">{value}</td></tr>'
        for label, value in safe_rows
    )
    plain_rows = "\n".join(f"{label}: {value}" for label, value in rows)
    plain = f"{heading}\n\n{description}\n\n{plain_rows}\n\n{note}\n\nЛичный кабинет: {CABINET_URL}"
    content = f"""<p style="margin:0 0 20px;color:#71717a;font-size:14px;line-height:1.6;">{escape(description)}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
<div style="margin-top:20px;padding:16px;border-left:3px solid #0184f8;border-radius:0 14px 14px 0;background:#f4f4f5;color:#71717a;font-size:13px;line-height:1.6;">{escape(note)}</div>
<p style="margin:24px 0 0;text-align:center;"><a href="{escape(CABINET_URL, quote=True)}" style="display:inline-block;padding:14px 22px;border-radius:12px;background:#0184f8;color:#fff;font-size:13px;font-weight:700;text-decoration:none;">Открыть личный кабинет</a></p>"""
    html = render_email_frame(heading=heading, eyebrow=eyebrow, content_html=content)
    return html, plain


def _send_email(email: str, subject: str, html_body: str, plain_body: str) -> None:
    host = (os.getenv("SMTP_HOST") or settings.SMTP_HOST or "").strip()
    user = (os.getenv("SMTP_USER") or settings.SMTP_USER or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or settings.SMTP_PASSWORD or "").strip()
    from_email = (os.getenv("SMTP_FROM_EMAIL") or settings.SMTP_FROM_EMAIL or user or "").strip()
    port = int(os.getenv("SMTP_PORT") or settings.SMTP_PORT or 587)
    if not host or not from_email:
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Lunet <{from_email}>"
    message["To"] = email
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            if user:
                server.login(user, password)
            server.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        if user:
            server.login(user, password)
        server.send_message(message)


class EmailNotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.activity = ActivityService(session)

    async def _already_sent(
        self,
        *,
        user_id: int,
        action: str,
        dedupe_key: str,
        subscription_id: int | None = None,
        transaction_id_ref: int | None = None,
    ) -> bool:
        query = select(UserActivity.id).where(
            UserActivity.user_id == user_id,
            UserActivity.action == action,
            UserActivity.note == f"dedupe:{dedupe_key}",
        )
        if subscription_id is not None:
            query = query.where(UserActivity.subscription_id == subscription_id)
        if transaction_id_ref is not None:
            query = query.where(UserActivity.transaction_id_ref == transaction_id_ref)
        return (await self.session.scalar(query.limit(1))) is not None

    async def _send_once(
        self,
        *,
        user,
        action: str,
        dedupe_key: str,
        subject: str,
        eyebrow: str,
        heading: str,
        description: str,
        rows: list[tuple[str, str]],
        note: str,
        subscription_id: int | None = None,
        transaction_id_ref: int | None = None,
    ) -> bool:
        user_id = int(user.id)
        email = str(getattr(user, "email", None) or "").strip().lower()
        if not email:
            return False
        try:
            if await self._already_sent(
                user_id=user_id,
                action=action,
                dedupe_key=dedupe_key,
                subscription_id=subscription_id,
                transaction_id_ref=transaction_id_ref,
            ):
                return False
        except Exception as exc:
            await self.session.rollback()
            logger.warning(
                "[email-notify] dedupe check failed user_id=%s action=%s error=%s",
                user_id,
                action,
                exc,
            )
            return False

        html_body, plain_body = _render_email(
            eyebrow=eyebrow,
            heading=heading,
            description=description,
            rows=rows,
            note=note,
        )
        try:
            await asyncio.to_thread(_send_email, email, subject, html_body, plain_body)
        except Exception as exc:
            logger.warning(
                "[email-notify] send failed user_id=%s action=%s email=%s error=%s",
                user_id,
                action,
                email,
                exc,
            )
            return False

        try:
            await self.activity.log_user_event(
                user_id=user_id,
                category="notification",
                action=action,
                source="email",
                subscription_id=subscription_id,
                transaction_id_ref=transaction_id_ref,
                note=f"dedupe:{dedupe_key}",
            )
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            logger.warning(
                "[email-notify] delivery log failed user_id=%s action=%s error=%s",
                user_id,
                action,
                exc,
            )
        return True

    async def payment_confirmed(self, *, user, transaction) -> bool:
        amount = int(getattr(transaction, "amount", 0) or 0)
        return await self._send_once(
            user=user,
            action="email_payment_confirmed",
            dedupe_key=f"payment:{transaction.id}",
            subject="Баланс пополнен — Lunet",
            eyebrow="ПОПОЛНЕНИЕ",
            heading="Платёж подтверждён",
            description="Средства успешно зачислены на ваш баланс Lunet.",
            rows=[("Сумма", f"{amount} ₽")],
            note="Баланс уже обновлён и доступен для оплаты подписки.",
            transaction_id_ref=int(transaction.id),
        )

    async def balance_credited(self, *, user, amount: int, reference: str) -> bool:
        return await self._send_once(
            user=user,
            action="email_balance_credited",
            dedupe_key=f"balance:{reference}",
            subject="Баланс пополнен — Lunet",
            eyebrow="ПОПОЛНЕНИЕ",
            heading="Баланс пополнен",
            description="Средства успешно зачислены на ваш баланс Lunet.",
            rows=[("Сумма", f"{int(amount)} ₽")],
            note="Баланс уже обновлён и доступен для оплаты подписки.",
        )

    async def gift_received(self, *, user, subscription, plan_name: str, sender: str) -> bool:
        period_key = getattr(subscription, "current_period_end", None)
        return await self._send_once(
            user=user,
            action="email_subscription_gift_received",
            dedupe_key=f"gift:{subscription.id}:{period_key.isoformat() if period_key else 'none'}",
            subject="Вам подарили подписку — Lunet",
            eyebrow="ПОДАРОК",
            heading="Вам подарили подписку",
            description="Подарочная подписка уже активирована в вашем аккаунте.",
            rows=[
                ("Тариф", plan_name),
                ("Действует до", _format_date(getattr(subscription, "current_period_end", None))),
                ("Отправитель", sender),
            ],
            note="Откройте личный кабинет, чтобы получить ссылку и подключить VPN.",
            subscription_id=int(subscription.id),
        )

    async def subscription_ending(self, *, user, subscription, hours: int) -> bool:
        remaining = "2 дня" if hours >= 48 else "1 день" if hours >= 24 else f"около {max(1, hours)} ч."
        period_key = getattr(subscription, "current_period_end", None)
        return await self._send_once(
            user=user,
            action="email_subscription_ending_soon",
            dedupe_key=f"ending:{subscription.id}:{period_key.isoformat() if period_key else 'none'}",
            subject="Подписка скоро закончится — Lunet",
            eyebrow="ПОДПИСКА",
            heading="Подписка скоро закончится",
            description="Продлите подписку заранее, чтобы VPN продолжил работать без перерыва.",
            rows=[
                ("Осталось", remaining),
                ("Дата окончания", _format_date(getattr(subscription, "current_period_end", None))),
            ],
            note="Если автопродление включено, убедитесь, что на балансе достаточно средств.",
            subscription_id=int(subscription.id),
        )

    async def subscription_expired(self, *, user, subscription) -> bool:
        period_key = getattr(subscription, "current_period_end", None)
        return await self._send_once(
            user=user,
            action="email_subscription_expired",
            dedupe_key=f"expired:{subscription.id}:{period_key.isoformat() if period_key else 'none'}",
            subject="Подписка закончилась — Lunet",
            eyebrow="ПОДПИСКА",
            heading="Ваша подписка закончилась",
            description="Доступ к VPN временно приостановлен.",
            rows=[("Дата окончания", _format_date(getattr(subscription, "current_period_end", None)))],
            note="Продлите подписку, и сервис снова заработает по вашей текущей ссылке.",
            subscription_id=int(subscription.id),
        )
