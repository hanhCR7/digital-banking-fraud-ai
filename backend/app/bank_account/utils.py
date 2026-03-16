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
        AccountCurrencyEnum.VND: settings.CURRENCY_CODE_VND,
    }

    currency_code = currency_codes.get(currency)

    if not currency_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": f"Hệ thống không hỗ trợ loại tiền tệ: {currency}"},
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
                detail={"status": "error", "message": "Chưa cấu hình mã ngân hàng hoặc mã chi nhánh."},
            )
        # Kiểm tra loại tiền tệ được hỗ trợ
        currency_code = get_currency_code(currency)
        # Tạo phần đầu của số tài khoản với mã ngân hàng, chi nhánh và loại tiền tệ
        prefix = f"{settings.BANK_CODE}{settings.BANK_BRANCH_CODE}{currency_code}"

        # Tổng độ dài số tài khoản = 16
        remaining_digits = 16 - len(prefix) - 1
        if remaining_digits <= 0:
            raise ValueError("Cấu hình số tài khoản không hợp lệ.")
        # Sinh phần còn lại của số tài khoản với các chữ số ngẫu nhiên
        random_digits = "".join(
            secrets.choice("0123456789") for _ in range(remaining_digits)
        )
        # Kết hợp phần đầu và phần ngẫu nhiên để tạo số tài khoản tạm thời (chưa có check digit)
        partial_account_number = f"{prefix}{random_digits}"
        # Tính check digit và hoàn thiện số tài khoản
        check_digit = calculate_luhn_check_digit(partial_account_number)
        # Trả về số tài khoản hoàn chỉnh
        return f"{partial_account_number}{check_digit}"

    except HTTPException as http_ex:
        logger.error(f"Xảy ra ngoại lệ HTTP trong quá trình tạo số tài khoản: {http_ex.detail}")
        raise
    except Exception as e:
        logger.error(f"Lỗi khi tạo số tài khoản: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Không thể tạo số tài khoản"},
        )

def normalize_vnd_amount(amount: Decimal) -> Decimal:
    """Chuẩn hóa số tiền"""
    if amount <= 0:
        raise ValueError("Số tiền phải lớn hơn 0")
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

