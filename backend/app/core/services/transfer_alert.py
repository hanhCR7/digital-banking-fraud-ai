from datetime import datetime
from decimal import Decimal

from backend.app.bank_account.enums import AccountCurrencyEnum
from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate
from backend.app.core.logging import get_logger
from backend.app.core.utils.number_format import format_currency

# Logger ghi log quá trình gửi email
logger = get_logger()


class TransferAlertEmail(EmailTemplate):
    """Email template thông báo giao dịch chuyển tiền."""

    template_name = "transfer_alert.html"        # Template HTML
    template_name_plain = "transfer_alert.txt"   # Template text
    subject = "Transfer Notification"             # Tiêu đề email


async def send_transfer_alert(
    *,
    sender_email: str,
    sender_name: str,
    receiver_email: str,
    receiver_name: str,
    sender_account_number: str,
    receiver_account_number: str,
    amount: Decimal,
    converted_amount: Decimal,
    sender_currency: AccountCurrencyEnum,
    receiver_currency: AccountCurrencyEnum,
    exchange_rate: Decimal | None = None,
    conversion_fee: Decimal | None = None,
    description: str,
    reference: str,
    transaction_date: datetime,
    sender_balance: Decimal,
    receiver_balance: Decimal,
) -> None:
    """Gửi email thông báo chuyển tiền cho sender và receiver."""

    try:
        # Kiểm tra giao dịch có chuyển đổi tiền tệ hay không
        conversion_applied = sender_currency != receiver_currency

        # Thông tin chung cho cả 2 email
        common_details = {
            "transaction_date": transaction_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "description": description,
            "reference": reference,
            "site_name": settings.SITE_NAME,
            "support_email": settings.SUPPORT_EMAIL,
        }

        # Context email cho người gửi
        sender_context = {
            **common_details,
            "is_sender": True,
            "user_name": sender_name,
            "counterparty_name": receiver_name,
            "counterparty_account": receiver_account_number,
            # Số tiền gửi (tiền của người gửi)
            "amount": format_currency(amount, sender_currency.value),
            "currency": sender_currency.value,
            # Số dư sau giao dịch của người gửi
            "user_balance": format_currency(
                sender_balance, sender_currency.value
            ),
            "conversion_applied": conversion_applied,
        }

        # Nếu có chuyển đổi tiền tệ, bổ sung thông tin chi tiết
        if conversion_applied:
            sender_context.update(
                {
                    # Số tiền sau chuyển đổi (tiền của người nhận)
                    "converted_amount": format_currency(
                        converted_amount, receiver_currency.value
                    ),
                    # Tỷ giá áp dụng
                    "exchange_rate": format_currency(
                        exchange_rate, receiver_currency.value
                    )
                    if exchange_rate
                    else "1.00",
                    # Phí chuyển đổi (trừ vào tiền người gửi)
                    "conversion_fee": format_currency(
                        conversion_fee, sender_currency.value
                    )
                    if conversion_fee
                    else "0.00",
                    "to_currency": receiver_currency.value,
                }
            )

        # Context email cho người nhận
        receiver_context = {
            **common_details,
            "is_sender": False,
            "user_name": receiver_name,
            "counterparty_name": sender_name,
            # Người nhận luôn thấy số tiền thực nhận
            "amount": format_currency(
                converted_amount if conversion_applied else amount,
                receiver_currency.value,
            ),
            "currency": receiver_currency.value,
            # Số dư sau giao dịch của người nhận
            "user_balance": format_currency(
                receiver_balance, receiver_currency.value
            ),
            "conversion_applied": conversion_applied,
        }

        # Nếu có chuyển đổi tiền tệ, bổ sung thông tin tiền gốc
        if conversion_applied:
            receiver_context.update(
                {
                    "original_amount": format_currency(
                        amount, sender_currency.value
                    ),
                    "from_currency": sender_currency.value,
                    "exchange_rate": format_currency(
                        exchange_rate, receiver_currency.value
                    )
                    if exchange_rate
                    else "1.00",
                }
            )

        # Gửi email
        await TransferAlertEmail.send_email(
            email_to=sender_email,
            context=sender_context,
        )

        await TransferAlertEmail.send_email(
            email_to=receiver_email,
            context=receiver_context,
        )

        # Log thành công
        logger.info(
            f"Transfer alert sent successfully. "
            f"Reference={reference}, "
            f"Sender={sender_email}, "
            f"Receiver={receiver_email}"
        )

    except Exception as e:
        # Log lỗi khi gửi email
        logger.error(
            f"Failed to send transfer alert. "
            f"Reference={reference}, Error={str(e)}"
        )
        raise