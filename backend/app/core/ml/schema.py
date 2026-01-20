from datetime import datetime
from typing import Dict, Optional, Any
from uuid import UUID
from enum import Enum
from pydantic import BaseModel
from sqlmodel import Field
from backend.app.core.ml.config import ml_settings
from backend.app.core.ml.models import MLModel



class TrainingRequest(BaseModel):
    """
    Request schema cho việc huấn luyện model ML
    """
    days_lookback: int = Field(
        default=ml_settings.DEFAULT_TRAINING_LOOKBACK_DAYS,
        description="Số ngày dữ liệu dùng để huấn luyện model",
    )

    hyperparams: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Hyperparameters tuỳ chỉnh cho model (n_estimators, learning_rate, ...)",
    )

    run_async: bool = Field(
        default=True,
        description="Chạy huấn luyện dưới dạng background task (Celery) hay không",
    )


class ModelResponse(BaseModel):
    """
    Schema mô tả thông tin chi tiết của một model ML
    """
    id: UUID
    name: str
    version: str
    status: str                       # Trạng thái model (training / trained / deployed)
    auc_score: float                  # AUC score trên tập validation
    precision: float
    recall: float
    f1_score: float
    created_at: datetime
    trained_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None
    mlflow_run_id: Optional[str] = None
    mlflow_model_uri: Optional[str] = None


class TrainingResponse(BaseModel):
    """
    Response schema cho API huấn luyện model
    """
    model: Optional[ModelResponse] = None      # Thông tin model sau khi train
    metrics: Optional[Dict[str, Any]] = None   # Metric chi tiết (accuracy, auc, ...)
    mlflow_ui_url: str                         # Link tới MLflow UI
    task_id: Optional[str] = None              # Celery task ID (nếu chạy async)
    status: str                                # success / failed / running
    message: str                               # Thông báo kết quả

class EvaluationRequest(BaseModel):
    """
    Request schema cho việc đánh giá model
    """
    model_id: UUID                             # ID model cần đánh giá
    start_date: Optional[datetime] = None      # Thời gian bắt đầu đánh giá
    end_date: Optional[datetime] = None        # Thời gian kết thúc đánh giá

class EvaluationResponse(BaseModel):
    """
    Response schema cho kết quả đánh giá model
    """
    model_id: UUID
    metrics: Dict[str, Any]                    # Metric đánh giá
    mlflow_ui_url: str                         # Link MLflow UI

class DeploymentRequest(BaseModel):
    """
    Request schema cho việc deploy model
    """
    model_id: UUID                             # ID model cần deploy

class DeploymentResponse(BaseModel):
    """
    Response schema cho việc deploy model
    """
    model: ModelResponse                       # Thông tin model sau khi deploy
    status: str                                # success / failed
    message: str                               # Thông báo kết quả
    mlflow_ui_url: str                         # Link MLflow UI

def model_to_response(model: MLModel) -> ModelResponse:
    """
    Chuyển đổi entity MLModel (ORM) sang ModelResponse (API schema)
    """
    return ModelResponse(
        id=model.id,
        name=model.name,
        version=model.version,
        status=model.status.value,
        auc_score=model.auc_score,
        precision=model.precision,
        recall=model.recall,
        f1_score=model.f1_score,
        created_at=model.created_at,
        trained_at=model.trained_at,
        deployed_at=model.deployed_at,
        mlflow_run_id=model.mlflow_run_id,
        mlflow_model_uri=model.mlflow_model_uri,
    )