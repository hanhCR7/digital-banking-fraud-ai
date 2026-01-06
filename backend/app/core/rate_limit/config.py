from pydantic import BaseModel


# Cấu hình giới hạn tần suất request cho từng API
class RateLimitConfig(BaseModel):
    max_requests: int            # Số request tối đa cho phép
    window_seconds: int          # Khoảng thời gian tính giới hạn (giây)
    block_on_exceed: bool = True # Có chặn request khi vượt giới hạn hay không


# Cấu hình rate limit mặc định cho từng endpoint
DEFAULT_RATE_LIMITS = {
    # Giới hạn request gửi OTP đăng nhập
    "/api/v1/auth/login/request-otp": RateLimitConfig(
        max_requests=3, window_seconds=60
    ),

    # Giới hạn đăng ký tài khoản mới
    "/api/v1/auth/register": RateLimitConfig(
        max_requests=3, window_seconds=3600
    ),

    # Giới hạn reset mật khẩu
    "/api/v1/auth/reset-password": RateLimitConfig(
        max_requests=3, window_seconds=3600
    ),

    # Giới hạn khởi tạo giao dịch chuyển tiền
    "/api/v1/bank-account/transfer/initiate": RateLimitConfig(
        max_requests=10, window_seconds=3600
    ),

    # Giới hạn rút tiền
    "/api/v1/bank-account/withdraw": RateLimitConfig(
        max_requests=10, window_seconds=3600
    ),

    # Giới hạn nạp tiền
    "/api/v1/bank-account/deposit": RateLimitConfig(
        max_requests=20, window_seconds=3600
    ),

    # Giới hạn tạo thẻ ảo (mỗi ngày)
    "/api/v1/virtual-card/create": RateLimitConfig(
        max_requests=5, window_seconds=86400
    ),

    # Giới hạn nạp tiền vào thẻ ảo
    "/api/v1/virtual-card/top-up": RateLimitConfig(
        max_requests=20, window_seconds=3600
    ),

    # Giới hạn upload hồ sơ người dùng
    "/api/v1/profile/upload": RateLimitConfig(
        max_requests=10, window_seconds=3600
    ),

    # Giới hạn tạo sao kê ngân hàng
    "/api/v1/bank-account/statement/generate": RateLimitConfig(
        max_requests=5, window_seconds=3600
    ),

    # Health check cho hệ thống (không chặn khi vượt giới hạn)
    "/health": RateLimitConfig(
        max_requests=500, window_seconds=60, block_on_exceed=False
    ),

    # Cấu hình mặc định cho các endpoint chưa được khai báo
    "default": RateLimitConfig(
        max_requests=100, window_seconds=60, block_on_exceed=False
    ),
}


# Danh sách endpoint được whitelist (không áp dụng rate limit)
RATE_LIMIT_WHITELIST = {"/health"}
