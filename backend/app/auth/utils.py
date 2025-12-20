import random
import string
import uuid
import jwt
from datetime import datetime, timedelta, timezone
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

def create_activation_token(id: uuid.UUID) -> str:
    """
    Tạo JWT token dùng cho việc kích hoạt tài khoản người dùng
    Token này sẽ được gửi kèm trong email kích hoạt
    """
    # Payload (nội dung) của JWT
    payload = {
        "id": str(id),  # ID người dùng (chuyển sang string để serialize)
        "type": "activation", # Chuyển trạng thái user -> kích hoạt
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACTIVATION_TOKEN_EXPIRATION_MINUTES),# Thời điểm token hết hạn (expiration time)
        "iat": datetime.now(timezone.utc),# Thời điểm token được tạo (issued at)
    }
    # Mã hóa payload thành JWT
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
