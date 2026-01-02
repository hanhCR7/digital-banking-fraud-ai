import secrets
from decimal import ROUND_HALF_UP, Decimal
from typing import Tuple

from fastapi import HTTPException, status

from backend.app.bank_account.enums import AccountCurrencyEnum
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()


def get_currency_code(currency: AccountCurrencyEnum) -> str:
    """
    Lấy mã tiền tệ nội bộ của ngân hàng dựa trên loại tiền tệ.
    Hàm này được sử dụng khi sinh số tài khoản ngân hàng.
    """
    # Bản đồ giữa enum tiền tệ và mã tiền tệ được cấu hình trong hệ thống
    currency_codes = {
        AccountCurrencyEnum.USD: settings.CURRENCY_CODE_USD,
        AccountCurrencyEnum.EUR: settings.CURRENCY_CODE_EUR,
        AccountCurrencyEnum.GBP: settings.CURRENCY_CODE_GBP,
        AccountCurrencyEnum.KES: settings.CURRENCY_CODE_KES,
        AccountCurrencyEnum.VND: settings.CURRENCY_CODE_VND,
    }

    currency_code = currency_codes.get(currency)

    # Trường hợp tiền tệ không hợp lệ hoặc chưa được cấu hình
    if not currency_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": f"Invalid currency: {currency}"},
        )

    return currency_code


def split_into_digits(number: str | int) -> list[int]:
    """
    Tách một số thành danh sách các chữ số riêng lẻ.
    Dùng trong thuật toán Luhn để tính check digit.
    """
    return [int(digit) for digit in str(number)]


def calculate_luhn_check_digit(number: str) -> int:
    """
    Tính chữ số kiểm tra (check digit) theo thuật toán Luhn.
    Thuật toán này giúp phát hiện lỗi nhập sai số tài khoản.
    """
    digits = split_into_digits(number)

    # Các chữ số ở vị trí lẻ (tính từ phải sang trái)
    odd_digits = digits[-1::-2]

    # Các chữ số ở vị trí chẵn
    even_digits = digits[-2::-2]

    total = sum(odd_digits)

    # Nhân đôi các chữ số chẵn và cộng tổng các chữ số
    for digit in even_digits:
        doubled = digit * 2
        total += sum(split_into_digits(doubled))

    # Tính check digit
    return (10 - (total % 10)) % 10


def generate_account_number(currency: AccountCurrencyEnum) -> str:
    """
    Sinh số tài khoản ngân hàng theo chuẩn nội bộ:
    [BANK_CODE][BRANCH_CODE][CURRENCY_CODE][RANDOM][CHECK_DIGIT]
    """
    try:
        # Kiểm tra cấu hình ngân hàng
        if not all([settings.BANK_CODE, settings.BANK_BRANCH_CODE]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "status": "error",
                    "message": "Bank or Branch code not configured",
                },
            )

        currency_code = get_currency_code(currency)

        # Prefix cố định của số tài khoản
        prefix = f"{settings.BANK_CODE}{settings.BANK_BRANCH_CODE}{currency_code}"

        # Tổng độ dài số tài khoản là 16 chữ số (bao gồm check digit)
        remaining_digits = 16 - len(prefix) - 1

        # Sinh các chữ số ngẫu nhiên
        random_digits = "".join(
            secrets.choice("0123456789") for _ in range(remaining_digits)
        )

        partial_account_number = f"{prefix}{random_digits}"

        # Tính chữ số kiểm tra theo Luhn
        check_digit = calculate_luhn_check_digit(partial_account_number)

        account_number = f"{partial_account_number}{check_digit}"

        return account_number

    except HTTPException as http_ex:
        logger.error(f"HTTP Exception in account number generation: {http_ex.detail}")
        raise http_ex
    except Exception as e:
        logger.error(f"Error generating account number: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": f"Failed to generate account number: {str(e)}",
            },
        )



