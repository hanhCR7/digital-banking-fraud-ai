from enum import Enum

class AIReviewStatusEnum(str, Enum):
    """
    Trạng thái đánh giá giao dịch / hành vi người dùng bởi hệ thống AI.

    Được sử dụng trong:
    - Fraud Detection
    - Transaction Monitoring
    - Risk Assessment
    """
    # Chờ AI xử lý / phân tích
    PENDING = "pending"
    # Phát hiện dấu hiệu bất thường, cần kiểm tra thêm
    FLAGGED = "flagged"
    # Được AI xác nhận là an toàn
    CLEARED = "cleared"
    # Xác nhận gian lận
    CONFIRMED_FRAUD = "confirmed_fraud"
    
