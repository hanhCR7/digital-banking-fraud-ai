import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel, Float

from backend.app.core.ml.enums import ModelStatusEnum


class MLModel(SQLModel, table=True):
    """Bảng lưu metadata của mô hình Machine Learning. """

    # Khóa chính UUID của model
    id: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True),
        default_factory=uuid.uuid4,
    )

    # Tên mô hình
    name: str = Field(index=True)

    # Phiên bản mô hình
    version: str = Field(index=True)

    # Trạng thái hiện tại của model
    status: ModelStatusEnum = Field(
        sa_column=Column(Enum(ModelStatusEnum), nullable=False),
        default=ModelStatusEnum.TRAINING,
    )

    # Các chỉ số đánh giá model
    auc_score: float = Field(
        sa_column=Column(Float, nullable=False, index=True),
        default=0.0,
    )
    precision: float = Field(default=0.0)
    recall: float = Field(default=0.0)
    f1_score: float = Field(default=0.0) 

    # Danh sách feature được sử dụng để huấn luyện
    features: list[str] = Field(
        sa_column=Column(pg.ARRAY(pg.VARCHAR))
    )

    # Hyperparameters của model (lưu dạng JSON)
    hyperparameters: dict = Field(
        sa_column=Column(JSONB)
    )

    # Kích thước dataset dùng để training
    training_dataset_size: int = Field(default=0)

    # Thông tin tracking MLflow
    mlflow_run_id: str | None = Field(default=None)
    mlflow_experiment_id: str | None = Field(default=None)
    mlflow_model_uri: str | None = Field(default=None)

    # Thời điểm tạo record model
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # Thời điểm model được huấn luyện xong
    trained_at: datetime | None = Field(
        default=None,
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True),
    )

    # Thời điểm model được deploy lên production
    deployed_at: datetime | None = Field(
        default=None,
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True),
    )

    # Quan hệ với bảng dự đoán
    predictions: list["ModelPrediction"] = Relationship(
        back_populates="model"
    )


class ModelPrediction(SQLModel, table=True):
    """
    Bảng lưu kết quả dự đoán của model cho từng giao dịch.
    """

    # Khóa chính UUID
    id: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True),
        default_factory=uuid.uuid4,
    )

    # Giao dịch được dự đoán
    transaction_id: uuid.UUID = Field(
        foreign_key="transaction.id",
        index=True,
    )

    # Model đã sử dụng để dự đoán
    model_id: uuid.UUID = Field(
        foreign_key="mlmodel.id",
        index=True,
    )

    # Điểm dự đoán (0 → 1)
    prediction_score: float = Field(ge=0, le=1)

    # Thời điểm dự đoán
    prediction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
    )

    # Feature đầu vào dùng cho lần dự đoán này
    input_features: dict = Field(
        sa_column=Column(JSONB)
    )

    # Nhãn thật (dùng cho training / evaluation sau này)
    true_label: bool | None = Field(default=None)

    # Run ID của MLflow tương ứng
    mlflow_run_id: str | None = Field(default=None)

    # Quan hệ ngược với model
    model: MLModel = Relationship(
        back_populates="predictions"
    )


class TrainingDataset(SQLModel, table=True):
    """
    Bảng lưu metadata của dataset dùng để huấn luyện model.
    """

    # Khóa chính UUID
    id: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True),
        default_factory=uuid.uuid4,
    )

    # Tên dataset
    name: str

    # Phiên bản dataset
    version: str

    # Thời điểm tạo dataset
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # Thống kê dataset
    total_samples: int
    fraud_samples: int
    legitimate_samples: int

    # Khoảng thời gian dữ liệu
    start_date: datetime = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
    )
    end_date: datetime = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
    )

    # Đường dẫn dataset
    dataset_path: str

    # Artifact URI trong MLflow (nếu có)
    mlflow_artifact_uri: str | None = Field(default=None)

    # Thông tin feature (schema, stats, preprocessing, ...)
    feature_info: dict = Field(
        sa_column=Column(JSONB)
    )
