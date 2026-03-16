import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import mlflow
from celery import Task

from backend.app.core.celery_app import celery_app
from backend.app.core.db import async_session
from backend.app.core.logging import get_logger
from backend.app.core.ml.config import (
    DEFAULT_PERFORMANCE_THRESHOLD,
    DEFAULT_TRAINING_LOOKBACK_DAYS,
    MLFLOW_TRACKING_URI,
)
# Thiết lập MLflow Tracking Server cho toàn bộ các task ML
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

logger = get_logger()

class MLModelTrainingTask(Task):
    """
    Custom Celery Task cho quá trình huấn luyện mô hình ML.
    Mục đính của class này:
    - Bắt và xử lý lỗi khi task training thất bại
    - Đảm bảo MLflow run luôn được kết thúc đúng cách
    - Tránh tình trạng MLflow run bị treo nếu task crash hoặc timeout
    """ 
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Hàm được Celery tự động gọi khi task xảy ra lỗi.
        Tham số:
        - exc: exception gây ra lỗi
        - task_id: ID của task Celery
        - args, kwargs: tham số truyền vào task
        - einfo: thông tin traceback chi tiết
        """
        logger.error(f"Huấn luyện mô hình ML thất bại: {exc}.")
        # Nếu vẫ còn MLflow run đang active thì kết thúc ngay, trnahs tình trạng bị treo trên MLTS
        if mlflow.active_run():
            mlflow.end_run()
        # Gọi lại xử lý lỗi mặc định cảu Celery
        super().on_failure(exc, task_id, args, kwargs, einfo)
@celery_app.task(
    base=MLModelTrainingTask,
    name="train_fraud_detection_model",
    bind=True,
    max_retries=2,
    soft_time_limit=1800
)
def train_fraud_detection_model(
    self,
    days_lookback: int = DEFAULT_TRAINING_LOOKBACK_DAYS,
    hyperparams: dict[str, Any] | None = None
) -> dict:
    """
    Celery task huấn luyện mô hình phát hiện gian lân giao dịch
    sự dụng Gradient Boosting trong khoản thời gian xác định.
    """
    # Nếu tồn tại Mlflow run đang mở từ trước thì kết thúc để tránh xung đột
    if mlflow.active_run():
        mlflow.end_run()
    try:
        logger.info("Bắt đầu huấn luyện mô hình phát hiện gian lận bằng Gradient Boosting")
        # Xác định khoản thời gian lấy dữ liệu huấn luyện
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_lookback)
        from backend.app.core.ml.training import ModelTrainer
        from backend.app.core.model_registry import load_models
        async def _train_model():
            """
            Hàm async thực hiện huấn luyện model:
            - Mở session bất đồng bộ
            - Khởi tạo trainer
            - Train model và lưu metadata vào database + MLflow
            """
            async with async_session() as session:
                # Load toàn bộ SQLAlchemy models theo đúng thứ tự
                load_models()
                trainer = ModelTrainer(session)
                # Thực hiện train model trong khoản thời gian chỉ định
                model_record, metrics = await trainer.train_model(
                    start_date=start_date,
                    end_date=end_date,
                    hyperparams=hyperparams
                )
                # Trả về thông tin model và metrics phục vụ tracking
                return {
                    "model_id": str(model_record.id),
                    "model_type": "gradient_boosting",
                    "model_version": model_record.version,
                    "training_start": start_date.isoformat(),
                    "training_end": end_date.isoformat(),
                    "metrics": metrics,
                    "mlflow_run_id": model_record.mlflow_run_id,
                    "mlflow_model_uri": model_record.mlflow_model_uri,
                }
        # Chạy hàm async trong context của Celery task (sync)
        result = asyncio.run(_train_model())
        logger.info(f"Huấn luyện mô hình thành công với ID: {result['model_id']}")
        # Đảm bảo kết thúc MLflow run sau khi train xong
        if mlflow.active_run():
            mlflow.end_run()
        return result
    except Exception as e:
        logger.error(f"Lỗi trong quá trình huấn luyện mô hình phát hiện gian lận: {e}")
        # Đóng MLflow run nếu xảy ra lỗi
        if mlflow.active_run():
            mlflow.end_run()
        # Retry Celery task sau 5 phút
        raise self.retry(exc=e, countdown=300)
@celery_app.task(name="auto_deploy_best_model", bind=True)
def auto_deploy_best_model(
    self, performance_threshold: float = DEFAULT_PERFORMANCE_THRESHOLD
) -> dict:
    """
    Celery task tự động đánh giá và triển khai (deploy) mô hình phát hiện gian lận tốt nhất
    dựa trên ngưỡng hiệu năng (AUC score).
    """

    try:
        logger.info("Đang tìm kiếm mô hình phát hiện gian lận tốt nhất để triển khai")

        from sqlmodel import desc, select
        from backend.app.core.model_registry import load_models
        from backend.app.core.ml.deployment import ModelDeployer
        from backend.app.core.ml.models import MLModel, ModelStatusEnum

        # Load toàn bộ SQLAlchemy models theo đúng thứ tự trước khi truy vấn
        load_models()
        async def _find_and_deploy_best_model():
            """
            Hàm async:
            - Tìm model READY có AUC cao nhất vượt ngưỡng
            - So sánh với model đang deploy
            - Quyết định có deploy model mới hay không
            """
            async with async_session() as session:
                # Truy vấn model có AUC cao nhất, đạt trạng thái READY và vượt ngưỡng
                stmt = (
                    select(MLModel)
                    .where(
                        MLModel.status == ModelStatusEnum.READY,
                        MLModel.auc_score >= performance_threshold
                    )
                    .order_by(desc(MLModel.auc_score))
                    .limit(1)
                )

                result = await session.exec(stmt)
                best_model = result.first()

                deployer = ModelDeployer(session)

                # Lấy model hiện đang được deploy (Production)
                current_model = await deployer.get_deployed_model()

                # Trường hợp không có model nào đạt ngưỡng
                if not best_model:
                    with mlflow.start_run(run_name="auto_deploy_no_action"):
                        mlflow.log_param("action", "no_action")
                        mlflow.log_param(
                            "reason",
                            f"no_model_above_threshold_{performance_threshold}",
                        )

                    return {
                        "status": "no_action",
                        "message": f"Không tìm thấy mô hình nào có điểm AUC ≥ {performance_threshold}",
                    }

                # Trường hợp model hiện tại tốt hơn hoặc bằng model candidate
                if current_model and current_model.auc_score >= best_model.auc_score:
                    with mlflow.start_run(run_name="auto_deploy_no_action"):
                        mlflow.log_param("action", "no_action")
                        mlflow.log_param("reason", "current_model_better")

                        mlflow.log_param("current_model_id", str(current_model.id))
                        mlflow.log_param("candidate_model_id", str(best_model.id))

                        mlflow.log_metric("current_model_auc", current_model.auc_score)
                        mlflow.log_metric("candidate_model_auc", best_model.auc_score)

                    return {
                        "status": "no_action",
                        "message": f"Mô hình hiện tại ({current_model.id}) có hiệu năng tốt hơn hoặc tương đương",
                    }

                # Trường hợp model mới tốt hơn -> tiến hành deploy
                with mlflow.start_run(run_name="auto_deploy"):
                    mlflow.log_param("action", "deploy")
                    mlflow.log_param("model_id", str(best_model.id))
                    mlflow.log_metric("model_auc", best_model.auc_score)

                    # Log thông tin model cũ nếu tồn tại
                    if current_model:
                        mlflow.log_param("previous_model_id", str(current_model.id))
                        mlflow.log_metric("previous_model_auc", current_model.auc_score)
                        mlflow.log_metric(
                            "auc_improvement",
                            best_model.auc_score - current_model.auc_score,
                        )

                    # Thực hiện deploy model
                    deployed_model = await deployer.deploy_model(best_model.id)

                    mlflow.log_param("deployment_success", True)
                    mlflow.log_param(
                        "deployed_at", datetime.now(timezone.utc).isoformat()
                    )

                return {
                    "status": "deployed",
                    "message": f"Triển khai thành công mô hình mới {deployed_model.id}",
                    "model": {
                        "id": str(deployed_model.id),
                        "name": deployed_model.name,
                        "version": deployed_model.version,
                        "auc_score": deployed_model.auc_score,
                    },
                }

        # Chạy hàm async trong Celery task (sync context)
        result = asyncio.run(_find_and_deploy_best_model())

        logger.info(f"Tác vụ tự động triển khai đã hoàn thành: {result['status']}")

        return result

    except Exception as e:
        # Log lỗi tổng thể của task auto-deploy
        logger.error(f"Lỗi trong tác vụ tự động triển khai: {e}")
        raise