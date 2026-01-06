import secrets
from datetime import datetime, timedelta
from typing import Tuple

from argon2 import PasswordHasher


def generate_visa_card_number() -> str:
    # Prefix "4" cho thẻ Visa
    prefix = "4"

    # Sinh ngẫu nhiên 15 chữ số đầu (chưa gồm check digit)
    partial_number = prefix + "".join(secrets.choice("0123456789") for _ in range(14))

    # Tính tổng theo thuật toán Luhn
    total = 0
    for i, digit in enumerate(reversed(partial_number)):
        digit = int(digit)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    # Tính check digit để tổng chia hết cho 10
    check_digit = (10 - (total % 10)) % 10

    # Trả về số thẻ Visa hợp lệ (16 chữ số)
    return f"{partial_number}{check_digit}"


def generate_cvv() -> Tuple[str, str]:
    # Sinh mã CVV gồm 3 chữ số ngẫu nhiên
    cvv = "".join(secrets.choice("0123456789") for _ in range(3))

    # Hash CVV bằng Argon2 để đảm bảo bảo mật
    ph = PasswordHasher()
    cvv_hash = ph.hash(cvv)

    # Trả về CVV gốc (chỉ dùng tạm thời) và CVV đã hash để lưu DB
    return cvv, cvv_hash


def verify_cvv(cvv: str, cvv_hash: str) -> bool:
    # Xác minh CVV người dùng nhập với CVV đã hash
    try:
        ph = PasswordHasher()
        return ph.verify(cvv_hash, cvv)
    except Exception:
        # Sai CVV hoặc hash không hợp lệ
        return False


def generate_card_expiry_date() -> datetime:
    # Lấy thời điểm hiện tại
    current_date = datetime.now()

    # Thẻ có hạn sử dụng 3 năm
    expiry_date = current_date + timedelta(days=365 * 3)

    # Chuẩn hóa ngày hết hạn về ngày cuối cùng của tháng
    if expiry_date.month == 12:
        expiry_date = expiry_date.replace(
            year=expiry_date.year + 1,
            month=1,
            day=1,
        )
    else:
        expiry_date = expiry_date.replace(
            month=expiry_date.month + 1,
            day=1,
        )

    # Lùi lại 1 ngày để lấy ngày cuối tháng
    expiry_date = expiry_date - timedelta(days=1)

    # Trả về ngày hết hạn thẻ
    return expiry_date
