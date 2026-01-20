import os
from typing import Any, Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """
    Cấu hình cho hệ thống Machine Learning & MLOps.

    Chịu trách nhiệm:
    - Cấu hình MLflow (tracking, experiment, registry)
    - Cấu hình đường dẫn lưu model & dataset
    - Định nghĩa các ngưỡng và tham số mặc định cho huấn luyện
    """

    # Địa chỉ MLflow Tracking Server
    # Có thể override bằng biến môi trường ML_MLFLOW_TRACKING_URI
    MLFLOW_TRACKING_URI: str = os.environ.get(
        "MLFLOW_TRACKING_URI",
        "http://mlflow:4000/",
    )

    # Tên experiment dùng trong MLflow
    MLFLOW_EXPERIMENT_NAME: str = "fraud_detection"

    # Tên registry dùng để quản lý các model đã train
    MLFLOW_MODEL_REGISTRY_NAME: str = "fraud_detection_models"

    # Đường dẫn lưu model đã train trên filesystem
    MODEL_STORAGE_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ml",
        "models",
    )

    # Đường dẫn lưu dataset đã chuẩn bị cho training
    DATASET_STORAGE_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ml",
        "datasets",
    )

    # Số ngày mặc định dùng để lấy dữ liệu training
    DEFAULT_TRAINING_LOOKBACK_DAYS: int = 90

    # Ngưỡng hiệu năng tối thiểu (ví dụ AUC/F1) để chấp nhận model
    DEFAULT_PERFORMANCE_THRESHOLD: float = 0.85

    # Tham số mặc định cho mô hình Gradient Boosting
    DEFAULT_GRADIENT_BOOSTING_PARAMS: Dict[str, Any] = {
        "n_estimators": 100,        # Số cây
        "learning_rate": 0.1,       # Tốc độ học
        "max_depth": 3,             # Độ sâu tối đa của mỗi cây
        "min_samples_split": 2,     # Số mẫu tối thiểu để split
        "min_samples_leaf": 1,      # Số mẫu tối thiểu ở lá
        "subsample": 0.8,           # Tỷ lệ lấy mẫu cho mỗi cây
        "random_state": 42,         # Seed để tái lập kết quả
    }

    # Ngưỡng risk score mặc định để đánh dấu giao dịch rủi ro
    DEFAULT_RISK_THRESHOLD: float = 0.7

    # Ngưỡng risk score cao để xử lý nghiêm ngặt (block / manual review)
    HIGH_RISK_THRESHOLD: float = 0.85

    # Cấu hình load biến môi trường
    model_config = SettingsConfigDict(
        env_file="../../.envs/.env.local",  # File .env
        env_ignore_empty=True,              # Bỏ qua biến env rỗng
        extra="ignore",                     # Bỏ qua biến không khai báo
        env_prefix="ML_",                   # Prefix cho biến môi trường
    )

    def __init__(self, **kwargs):
        """
        Khởi tạo settings và đảm bảo các thư mục cần thiết tồn tại.
        """
        super().__init__(**kwargs)

        # Tạo thư mục lưu model nếu chưa tồn tại
        os.makedirs(self.MODEL_STORAGE_PATH, exist_ok=True)

        # Tạo thư mục lưu dataset nếu chưa tồn tại
        os.makedirs(self.DATASET_STORAGE_PATH, exist_ok=True)


# Instance settings dùng chung toàn hệ thống
ml_settings = MLSettings()

# Các biến export tiện dùng cho module khác
MLFLOW_TRACKING_URI = ml_settings.MLFLOW_TRACKING_URI
MLFLOW_EXPERIMENT_NAME = ml_settings.MLFLOW_EXPERIMENT_NAME
MLFLOW_MODEL_REGISTRY_NAME = ml_settings.MLFLOW_MODEL_REGISTRY_NAME

MODEL_STORAGE_PATH = ml_settings.MODEL_STORAGE_PATH
DATASET_STORAGE_PATH = ml_settings.DATASET_STORAGE_PATH

DEFAULT_TRAINING_LOOKBACK_DAYS = ml_settings.DEFAULT_TRAINING_LOOKBACK_DAYS
DEFAULT_PERFORMANCE_THRESHOLD = ml_settings.DEFAULT_PERFORMANCE_THRESHOLD

DEFAULT_GRADIENT_BOOSTING_PARAMS = ml_settings.DEFAULT_GRADIENT_BOOSTING_PARAMS
DEFAULT_RISK_THRESHOLD = ml_settings.DEFAULT_RISK_THRESHOLD
HIGH_RISK_THRESHOLD = ml_settings.HIGH_RISK_THRESHOLD
