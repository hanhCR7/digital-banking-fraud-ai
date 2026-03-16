from datetime import datetime
from decimal import Decimal

from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate
from backend.app.core.logging import get_logger
from backend.app.core.utils.number_format import format_currency

logger = get_logger()


class TransferAlertEmail(EmailTemplate):
    """Email template thông báo giao dịch chuyển tiền (VND-only)."""

    template_name = "transfer_alert.html"
    template_name_plain = "transfer_alert.txt"
    subject = "Thông báo chuyển tiền"


async def send_transfer_alert(
    *,
    sender_email: str,
    sender_name: str,
    receiver_email: str,
    receiver_name: str,
    sender_account_number: str,
    receiver_account_number: str,
    amount: Decimal,
    description: str,
    reference: str,
    transaction_date: datetime,
    sender_balance: Decimal,
    receiver_balance: Decimal,
) -> None:
    """
    Gửi email thông báo chuyển tiền (VND-only).
    """

    try:
        common_context = {
            "transaction_date": transaction_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "description": description,
            "reference": reference,
            "site_name": settings.SITE_NAME,
            "support_email": settings.SUPPORT_EMAIL,
            "currency": "VND",
        }

        # Email cho người gửi
        sender_context = {
            **common_context,
            "is_sender": True,
            "user_name": sender_name,
            "counterparty_name": receiver_name,
            "counterparty_account": receiver_account_number,
            "amount": format_currency(amount),
            "user_balance": format_currency(sender_balance),
        }

        # Email cho người nhận
        receiver_context = {
            **common_context,
            "is_sender": False,
            "user_name": receiver_name,
            "counterparty_name": sender_name,
            "counterparty_account": sender_account_number,
            "amount": format_currency(amount),
            "user_balance": format_currency(receiver_balance),
        }

        await TransferAlertEmail.send_email(
            email_to=sender_email,
            context=sender_context,
        )

        await TransferAlertEmail.send_email(
            email_to=receiver_email,
            context=receiver_context,
        )

        logger.info(
            "Transfer alert sent successfully | "
            f"Reference={reference} | "
            f"Sender={sender_email} | Receiver={receiver_email}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send transfer alert | "
            f"Reference={reference} | Error={str(e)}"
        )
        raise
