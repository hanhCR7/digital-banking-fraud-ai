from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """
    Cấu hình cho hệ thống AI / Risk Scoring.

    Dùng để:
    - Đánh giá rủi ro giao dịch
    - Phát hiện hành vi bất thường (fraud detection)
    - Điều chỉnh ngưỡng và trọng số mà không cần sửa code
    """

    # Ngưỡng điểm rủi ro tổng để đánh dấu giao dịch đáng ngờ
    RISK_SCORE_THRESHOLD: Decimal = Decimal("0.7")

    # Phiên bản mô hình AI (phục vụ tracking / audit)
    MODEL_VERSION: str = "1.0.0"

    # Số ngày dữ liệu lịch sử dùng để phân tích hành vi
    ANALYSIS_WINDOW_DAYS: int = 90

    # Trọng số cho từng yếu tố rủi ro chính
    RISK_WEIGHTS: dict[str, Decimal] = {
        "amount": Decimal("0.3"),           # Số tiền giao dịch
        "time": Decimal("0.1"),             # Thời điểm giao dịch
        "frequency": Decimal("0.2"),        # Tần suất giao dịch
        "pattern": Decimal("0.2"),          # Mẫu hành vi
        "velocity_amount": Decimal("0.2"),  # Tốc độ tăng số tiền
    }

    # Trọng số cho các mẫu hành vi bất thường
    PATTERN_WEIGHTS: dict[str, Decimal] = {
        "round_amounts": Decimal("0.2"),    # Số tiền tròn bất thường
        "repeated_amounts": Decimal("0.2"),# Lặp lại cùng số tiền
        "velocity": Decimal("0.6"),         # Tốc độ giao dịch dồn dập
    }

    # Trọng số cho rủi ro theo thời gian
    TIME_RISK_WEIGHTS: dict[str, Decimal] = {
        "time_of_day": Decimal("0.7"),      # Giờ giao dịch trong ngày
        "day_of_week": Decimal("0.3"),      # Ngày trong tuần
    }

    # Ngưỡng số tiền cao để đánh dấu giao dịch rủi ro
    HIGH_AMOUNT_THRESHOLD: Decimal = Decimal("50000000") # 10 triệu VND

    # Ngưỡng tổng số tiền giao dịch trong thời gian ngắn
    VELOCITY_THRESHOLD: Decimal = Decimal("50000000") # 50 triệu VND

    # Ngưỡng số lần giao dịch trong cửa sổ phân tích
    FREQUENCY_THRESHOLD: int = 5

    # Ngưỡng điểm rủi ro cao (dùng để trigger block / manual review)
    HIGH_RISK_SCORE_THRESHOLD: Decimal = Decimal("0.7")

    # Giờ bắt đầu giờ làm việc ngân hàng
    BANKING_HOURS_START: int = 9

    # Giờ kết thúc giờ làm việc ngân hàng
    BANKING_HOURS_END: int = 17

    # Rủi ro khi giao dịch trong giờ hành chính
    BANKING_HOURS_RISK: Decimal = Decimal("0.1")

    # Rủi ro khi giao dịch ngoài giờ hành chính
    OFF_HOURS_RISK: Decimal = Decimal("0.5")

    # Rủi ro rất cao khi giao dịch khuya / bất thường
    LATE_HOURS_RISK: Decimal = Decimal("0.9")

    # Cấu hình load biến môi trường
    model_config = SettingsConfigDict(
        env_file="../../.envs/.env.local",  # File .env
        env_ignore_empty=True,              # Bỏ qua biến env rỗng
        extra="ignore",                     # Bỏ qua biến thừa
        env_prefix="AI_",                   # Prefix cho biến môi trường
    )


# Instance dùng chung toàn hệ thống
ai_settings = AISettings()
