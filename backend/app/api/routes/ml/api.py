from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import mlflow
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.security import require_role
from backend.app.role.schema import RoleChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.ml.config import ml_settings
from backend.app.core.ml.deployment import ModelDeployer
from backend.app.core.ml.evaluation import ModelEvaluator
from backend.app.core.ml.models import MLModel, ModelStatusEnum
from backend.app.core.ml.training import ModelTrainer
from backend.app.core.tasks.ml import (
    auto_deploy_best_model,
    train_fraud_detection_model,
)
from backend.app.core.ml.schema import (
    TrainingRequest, ModelResponse,
    TrainingResponse, EvaluationRequest,
    EvaluationResponse, DeploymentRequest,
    DeploymentResponse, model_to_response
)

logger = get_logger()

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post(
    "/train/default",
    response_model=TrainingResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def train_model_with_defaults(
    session: AsyncSession = Depends(get_session)
):
    """
    Khởi chạy huấn luyện model gian lận với cấu hình mặc định
    - Chỉ dành cho admin
    - Huấn luyện chạy nền bằng Celery
    - Trả về task_id theo dõi trạng thái
    """
    # Tạo request với cấu hình huấn luyện mặc định
    request = TrainingRequest()
    # Thiết lập MLflow tracking server
    mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)
    # Gửi task huấn luyện model chạy nền
    task = train_fraud_detection_model.delay(
        days_lookback=request.days_lookback,
        hyperparams=request.hyperparams
    )
    # Trả response cho client
    return TrainingResponse(
        model=None,                              # Model chưa sẵn sàng (chạy async)
        metrics=None,                            # Metric sẽ có sau khi train xong
        mlflow_ui_url="http://mlflow.localhost/",  # Link MLflow UI
        task_id=task.id,                         # Celery task ID
        status="training_started",
        message="Mô hình đang được huấn luyện ngầm với cấu hình mặc định.”"
    )
@router.post(
    "/train",
    response_model=TrainingResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def train_model(
    request: TrainingRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Api huấn luyện mô hình phát hiện gian lận .
    - Hỗ trợ 2 chế độ:
      + Async: Chạy training bằng Celery(background)
      + Sync: Chạy training trực tiếp và trả kết quả ngay
    """
    # Thiết lập MLflow Tracking URI cho request hiện tại
    mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)
    # Chế độ Async(Background training bằng Celery)
    if request.run_async:
        # Gửi task huấn luyện model vào hàng đợi Celery
        task = train_fraud_detection_model.delay(
            days_lookback=request.days_lookback,
            hyperparams=request.hyperparams
        )
        # Trả về ngay cho client thông tin task
        return TrainingResponse(
            model=None,
            metrics=None,
            mlflow_ui_url="http://mlflow.localhost/",
            task_id=task.id,
            status="training_started",
            message="Mô hình đang được huấn luyện. Vui lòng theo dõi trạng thái để biết tiến độ."
        )
    # Chế độ Sync(Training trực tiếp trong request)
    # Khởi tạo trainer với DB session hiện tại
    trainer = ModelTrainer(session)
    # Xác định khoảng thời gian lấy dữ liệu huấn luyện
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=request.days_lookback)
    try:
        # Thực hiện huấn luyện model
        model_record, metrics = await trainer.train_model(
            start_date=start_date,
            end_date=end_date,
            hyperparams=request.hyperparams
        )
        # Trả về kết quả training nếu thành công
        return TrainingResponse(
            model=model_to_response(model_record),
            metrics=metrics,
            mlflow_ui_url=f"http://mlflow.localhost/experiments/{trainer.experiment_id}",
            status="success",
            message="Huấn luyện mô hình hoàn tất."
        )
    except Exception as e:
        raise HTTPException(
            status_code=300,
            detail=f"Huấn luyện mô hình thất bại: {str(e)}"
        )
@router.get(
    "/models",
    response_model=List[ModelResponse],
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def list_models(
    status: Optional[str] = None,
    limit: int = 10,
    session: AsyncSession = Depends(get_session)
):
    """
    API lấy danh sách các mô hình Machine Learning đã được huấn luyện
    - Chỉ admin được phép truy cập
    - Hỗ trợ lọc theo trạng thái model(status)
    - Giới hạn số lượng kết quả về 
    """
    from sqlmodel import desc, select
    # Khởi tạo query cơ bản
    # - Lấy từ bảng Model
    # - Sắp xếp theo thời gian tạo mới nhất
    # - Giới hạn số lượng bản ghi
    query = (
        select(MLModel)
        .order_by(desc(MLModel.created_at))
        .limit(limit)
    )
    # Nếu client truyền tham số status thì tiến hành lọc
    if status:
        try:
            # Chuyển string status sang Enum để đảm bảo hợp lệ
            status_enum = ModelStatusEnum(status)
            # Thêm điều kiện lọc theo trạng thái
            query = query.where(MLModel.status == status_enum)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail= f"Trạng thái bạn chọn không hợp lệ. Vui lòng chọn một trong các giá trị: {[s.value for s in ModelStatusEnum]}."
            )
    # Thực thi query bất đồng bộ
    result = await session.exec(query)
    # Lấy toàn bộ danh sách model
    models = result.all()
    # Chuyển model DB sang response schema
    return [model_to_response(model) for model in models]
@router.get(
    "/models/{model_id}",
    response_model=ModelResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def get_model(
    model_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """
    API lấy thông tin chi tiết của một mô hình Machine Learing theo ID
    - Trả về đầy đủ metadata của model 
    """
    # Lấy model theo khóa chính(UUID)
    model = await session.get(MLModel, model_id)
    # Trường hợp không tìm thấy model
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id} không tồn tại."
        )
    # Chuyển model DB sang response schema
    return model_to_response(model)
@router.get(
    "/status",
    response_model= Dict[str, Any],
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def get_ml_status(
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    API lấy trạng thái tổng quan của hệ thống Machine Learning
    Bao gồm:
    - Model hiện đang được deploy(nếu có)
    - Thống kê số lượng model theo từng trạng thái
    - Link tới MLflow UI
    """
    # Khởi tạo deployer để lấy model đang đưuọc deploy
    deployer = ModelDeployer(session)
    # Lấy model hiện tại đang ở trạng thái DEPLOYED (Production)
    deployed_model = await deployer.get_deployed_model()

    from sqlmodel import func, select
    # Dictionary lưu số lượng model theo từng trạng thái
    status_counts = {}
    # Lặp qua tất cả các trạng thái trong enum
    for status_enum in ModelStatusEnum:
        # Đếm số có trạng thái tương ứng
        stmt = select(func.count()).where(MLModel.status == status_enum)
        result = await session.exec(stmt)
        # one() trả về số lượng (count)
        count = result.one()
        status_counts[status_enum.value] = count
    # Trả về trạng thái tổng quan hệ thống ML
    return {
        #Cho biết hệ thống hiện có model đang deploy hay không
        "has_deployed_model": deployed_model is not None,
        # Thông tin chi tiết model đang deploy(nếu có)
        "model_details": (
            {
                "id": str(deployed_model.id),
                "name": deployed_model.name,
                "version": deployed_model.version,
                "metrics": {
                    "auc": deployed_model.auc_score,
                    "precision": deployed_model.precision,
                    "recall": deployed_model.recall,
                    "f1_score": deployed_model.f1_score,
                },
                "deployed_at": (
                    deployed_model.deployed_at.isoformat()
                    if deployed_model.deployed_at
                    else None
                ),
            }
            if deployed_model
            else None
        ),
        # Thống kê số lượng model theo từng trạng thái 
        "model_counts": status_counts,
        # Link tới MLflow UI để theo dõi experiment & model
        "mlflow_url": "http://mlflow.localhost/"
    }
@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def evaluate_model(
    request: EvaluationRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    API đánh giá (evaluate) hiệu năng của một mô hình Machine Learning
    trong một khoảng thời gian dữ liệu xác định
    - Kết quả đánh giá được log vào mlflow
    """
    # Thiết lập MLflow Tracking Server
    mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)
    # Khởi tạo evaluator với DB session
    evaluator = ModelEvaluator(session) 
    try:
        # Thực hiện đánh giá hiệu năng model
        results = await evaluator.evaluate_model_performance(
            model_id=request.model_id,
            start_date=request.start_date,
            end_date=request.end_date
        )
        # Trả về kết quả đánh giá cho client
        return {
            "model_id": request.model_id,
            "metrics": results,
            "mlflow_ui_url": f"http://mlflow.localhost/experiments/{evaluator.experiment_id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Không thể đánh giá mô hình. Lỗi: {str(e)}"
        )
@router.post(
    "/deploy",
    response_model=DeploymentResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def deploy_model(
    request: DeploymentRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    API triển khai một mô hình Machine Learning lên môi trường production
    - Cập nhật trạng thái model trong database
    - Đồng bộ trạng thái với MLflow Model Registry
    """
    # THiết lập MLflow Tracking Server
    mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)
    # Khởi tạo deployer vưới DB session
    deployer = ModelDeployer(session)
    try:
        # Thực hiện deploy model theo ID
        model = await deployer.deploy_model(model_id=request.model_id)
        # Trả về thông tin model sau khi deploy thành công
        return {
            "model": model_to_response(model),
            "status": "deployed",
            "message": f"Model {request.model_id} được triển khai thành công.",
            "mlflow_ui_url": f"http://mlflow.localhost/models/{ml_settings.MLFLOW_MODEL_REGISTRY_NAME}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Không thể triển khai mô hình. Lỗi: {str(e)}"
        )
@router.post(
    "/auto-deploy",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def trigger_auto_deploy(performance_threshold: float = 0.0) -> dict:
    """
    API kích hoạt quá trình triển khai (auto-deploy) mô hình tốt nhất
    - Task auto-deploy sẽ chạy nền bằng Celery
    - API trả về ngay task_id để client theo dõi trạng thái
    """
    # Gửi task auto-deploy vào hàng đợi Celery
    task = auto_deploy_best_model.delay(performance_threshold)
    # Trả về thông tin task cho client
    return {
        "status": "success",
        "message": "Quá trình tự động triển khai đang được thực hiện.",
        "task_id": task.id
    }