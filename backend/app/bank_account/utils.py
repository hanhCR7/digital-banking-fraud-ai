# Tiện ích sinh số tài khoản và xử lý chuyển đổi tiền tệ

import secrets
from decimal import ROUND_HALF_UP, Decimal
from typing import Tuple

from fastapi import HTTPException, status

from backend.app.bank_account.enums import AccountCurrencyEnum
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()


def get_currency_code(currency: AccountCurrencyEnum) -> str:
    """Lấy mã tiền tệ nội bộ theo loại tiền."""
    currency_codes = {
        AccountCurrencyEnum.USD: settings.CURRENCY_CODE_USD,
        AccountCurrencyEnum.EUR: settings.CURRENCY_CODE_EUR,
        AccountCurrencyEnum.GBP: settings.CURRENCY_CODE_GBP,
        AccountCurrencyEnum.KES: settings.CURRENCY_CODE_KES
    }

    currency_code = currency_codes.get(currency)

    if not currency_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": f"Invalid currency: {currency}"},
        )

    return currency_code


def split_into_digits(number: str | int) -> list[int]:
    """Tách số thành các chữ số (phục vụ thuật toán Luhn)."""
    return [int(digit) for digit in str(number)]


def calculate_luhn_check_digit(number: str) -> int:
    """Tính check digit theo thuật toán Luhn."""
    digits = split_into_digits(number)

    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]

    total = sum(odd_digits)

    for digit in even_digits:
        doubled = digit * 2
        total += sum(split_into_digits(doubled))

    return (10 - (total % 10)) % 10


def generate_account_number(currency: AccountCurrencyEnum) -> str:
    """
    Sinh số tài khoản ngân hàng:
    [BANK_CODE][BRANCH_CODE][CURRENCY_CODE][RANDOM][CHECK_DIGIT]
    """
    try:
        # Kiểm tra cấu hình ngân hàng
        if not all([settings.BANK_CODE, settings.BANK_BRANCH_CODE]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": "Bank or Branch code not configured"},
            )

        currency_code = get_currency_code(currency)

        prefix = f"{settings.BANK_CODE}{settings.BANK_BRANCH_CODE}{currency_code}"

        # Tổng độ dài số tài khoản = 16
        remaining_digits = 16 - len(prefix) - 1

        random_digits = "".join(
            secrets.choice("0123456789") for _ in range(remaining_digits)
        )

        partial_account_number = f"{prefix}{random_digits}"

        check_digit = calculate_luhn_check_digit(partial_account_number)

        return f"{partial_account_number}{check_digit}"

    except HTTPException as http_ex:
        logger.error(f"HTTP Exception in account number generation: {http_ex.detail}")
        raise
    except Exception as e:
        logger.error(f"Error generating account number: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to generate account number"},
        )


# Bảng tỷ giá giả lập (không phải realtime)
EXCHANGE_RATES = {
    "USD": {"EUR": Decimal("0.93"), "GBP": Decimal("0.79"), "KES": Decimal("163.50")},
    "EUR": {"USD": Decimal("1.0753"), "GBP": Decimal("0.8495"), "KES": Decimal("175.81")},
    "GBP": {"USD": Decimal("1.2658"), "EUR": Decimal("1.1772"), "KES": Decimal("206.96")},
    "KES": {"USD": Decimal("0.0061"), "EUR": Decimal("0.0057"), "GBP": Decimal("0.0048")},
}

CONVERSION_FEE_RATE = Decimal("0.005")  # Phí chuyển đổi 0.5%


def get_exchange_rate(
    from_currency: AccountCurrencyEnum,
    to_currency: AccountCurrencyEnum,
) -> Decimal:
    """Lấy tỷ giá giữa hai loại tiền."""
    if from_currency == to_currency:
        return Decimal("1.0")

    try:
        # Truy xuất tỷ giá từ bảng giả lập
        rate = EXCHANGE_RATES[from_currency.value][to_currency.value]
        return rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": f"Exchange rate not available for {from_currency.value} to {to_currency.value}",
            },
        )


def calculate_conversion(
    amount: Decimal,
    from_currency: AccountCurrencyEnum,
    to_currency: AccountCurrencyEnum,
) -> Tuple[Decimal, Decimal, Decimal]:
    """Tính số tiền sau khi chuyển đổi (đã trừ phí)."""

    if from_currency == to_currency:
        return amount, Decimal("1.0"), Decimal("0")
    # Lấy tỷ giá
    exchange_rate = get_exchange_rate(from_currency, to_currency)
    # Tính phí chuyển đổi
    conversion_fee = (amount * CONVERSION_FEE_RATE).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    # Tính số tiền sau phí
    amount_after_fee = amount - conversion_fee
    # Tính số tiền sau chuyển đổi
    converted_amount = (amount_after_fee * exchange_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return converted_amount, exchange_rate, conversion_fee
