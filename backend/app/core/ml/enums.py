from enum import Enum

class ModelStatusEnum(str, Enum):
    """Trạng thái vòng đời của mô hình AI."""

    TRAINING = "training"   # Mô hình đang trong quá trình huấn luyện
    READY = "ready"         # Huấn luyện xong, sẵn sàng deploy
    DEPLOYED = "deployed"   # Đang được sử dụng trong production
    FAILED = "failed"       # Huấn luyện thất bại hoặc lỗi nghiêm trọng
    ARCHIVED = "archived"   # Mô hình cũ, lưu trữ để audit / rollback

class ModelTypeEnum(str, Enum):
    """Loại mô hình AI được sử dụng trong hệ thống."""
    GRADIENT_BOOSTING = "gradient_boosting"  # Thuật toán Gradient Boosting
