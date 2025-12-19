import random
import string

from backend.app.core.config import settings
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Mã hóa mật khẩu sử dụng Argin2
_ph = PasswordHasher()

def generate_otp(length: int =6) -> str:
    """Tạo mã OTP gồm các chữ số ngẫu nhiên."""
    otp = "".join(random.choices(string.digits, k=length))
    return otp

def generate_password_hash(password: str) -> str:
    """Mã hóa mật khẩu sử dụng Argon2."""
    return _ph.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Xác minh mật khẩu với mật khẩu đã mã hóa."""
    try:
        return _ph.verify(hashed_password, password)
    except VerifyMismatchError:
        return False
    
def generate_username() -> str:
    """Tạo tên người dùng ngẫu nhiên dựa trên tên ngân hàng."""
    bank_name = settings.SITE_NAME
    # Lấy chữ cái đầu của mỗi từ trong tên ngân hàng
    words = bank_name.split()
    # Tạo tiền tố từ chữ cái đầu
    prefix = "".join([word[0] for word in words]).upper()
    # Tạo phần còn lại của tên người dùng với các ký tự ngẫu nhiên
    remaining_length = 12 - len(prefix) - 1
    # Đảm bảo remaining_length không âm
    random_string = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=remaining_length)
    )
    # Kết hợp tiền tố và phần ngẫu nhiên để tạo tên người dùng
    username = f"{prefix}-{random_string}"
    return username