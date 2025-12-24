import random
import string
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Response
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
# Tạo JWT token dùng cho việc xác thực người dùng (login)
def create_jwt_token(id: uuid.UUID, type: str = settings.COOKIE_ACCESS_NAME) -> str:
    if type == settings.COOKIE_ACCESS_NAME:
        expire_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRATION_MINUTES)
    else:
        expire_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRATION_DAYS)

    payload = {
        "id": str(id),
        "type": type,
        "exp": datetime.now(timezone.utc) + expire_delta,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)
def set_auth_cookies(
    response: Response, access_token: str, refresh_token: str | None = None
) -> None:
    """
    Hàm thiết lập các cookie xác thực sau khi đăng nhập hoặc làm mới token.
    """

    # Cấu hình chung cho tất cả cookie xác thực
    cookie_settings = {
        "path": settings.COOKIE_PATH,          # Cookie áp dụng cho toàn bộ website
        "secure": settings.COOKIE_SECURE,      # Chỉ gửi cookie qua HTTPS (prod)
        "httponly": settings.COOKIE_HTTP_ONLY, # Ngăn JavaScript truy cập cookie (chống XSS)
        "samesite": settings.COOKIE_SAMESITE,  # Hạn chế gửi cookie cross-site (chống CSRF)
    }

    # Thiết lập cookie access_token (JWT) – thời gian sống ngắn, dùng để xác thực API
    access_cookie_settings = cookie_settings.copy()
    access_cookie_settings["max_age"] = (
        settings.JWT_ACCESS_TOKEN_EXPIRATION_MINUTES * 60
    )
    response.set_cookie(
        settings.COOKIE_ACCESS_NAME, access_token, **access_cookie_settings
    )

    # Thiết lập cookie refresh_token (JWT) – thời gian sống dài, dùng để làm mới access_token
    # Chỉ set khi refresh_token tồn tại
    if refresh_token:
        refresh_cookie_settings = cookie_settings.copy()
        refresh_cookie_settings["max_age"] = (
            settings.JWT_REFRESH_TOKEN_EXPIRATION_DAYS * 24 * 60 * 60
        )
        response.set_cookie(
            settings.COOKIE_REFRESH_NAME,
            refresh_token,
            **refresh_cookie_settings,
        )

    # Cookie logged_in KHÔNG chứa dữ liệu nhạy cảm
    # Dùng cho frontend xác định trạng thái đăng nhập (hiển thị UI)
    # Không đặt HttpOnly để JavaScript có thể đọc được
    logged_in_cookie_settings = cookie_settings.copy()
    logged_in_cookie_settings["httponly"] = False
    logged_in_cookie_settings["max_age"] = (
        settings.JWT_ACCESS_TOKEN_EXPIRATION_MINUTES * 60
    )
    response.set_cookie(
        settings.COOKIE_LOGGED_IN_NAME,
        "true",
        **logged_in_cookie_settings,
    )
def delete_auth_cookies(response: Response) -> None:
    """Xoá toàn bộ cookie xác thực khi người dùng đăng xuất (logout)."""
    # Xoá cookie chứa access token (JWT)
    response.delete_cookie(settings.COOKIE_ACCESS_NAME)
    # Xoá cookie chứa refresh token (JWT)
    response.delete_cookie(settings.COOKIE_REFRESH_NAME)
    # Xoá cookie trạng thái đăng nhập dùng cho frontend
    response.delete_cookie(settings.COOKIE_LOGGED_IN_NAME)
# Tạo token đặt lại mật khẩu
def create_password_reset_token(id: uuid.UUID) -> str:
    """"Tạo token dùng trong việc đặt lại mật khẩu"""
    payload = {
        "id": str(id),
        "type": "password_reset",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRATION_MINUTES),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )