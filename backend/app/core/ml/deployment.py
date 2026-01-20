from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

import mlflow
from mlflow.sklearn import load_model
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.ai.enums import AIReviewStatusEnum
from backend.app.core.logging import get_logger
from backend.app.core.ml.config import ml_settings
from backend.app.core.ml.models import MLModel, ModelPrediction, ModelStatusEnum
from backend.app.transaction.enums import TransactionStatusEnum
from backend.app.transaction.models import Transaction

logger = get_logger()

class ModelDeployer:
    def __init__(self, session: AsyncSession):
        """
        Khởi tạo service triển khai (deploy) mô hình ML.
        Trách nhiệm:
        - Lưu database session để cập nhật trạng thái model
        - Thiết lập MLflow Tracking URI để thao tác với Model Registry
        """
        self.session = session
        # Thiết lập MLflow Tracking Server cho toàn bộ luồng deploy
        mlflow.set_tracking_uri(
            ml_settings.MLFLOW_TRACKING_URI
        )
    async def deploy_model(self, model_id: UUID)-> MLModel:
        """
        Deploy một mô hình ML vào môi trường production
        Quy trình:
        1. Kiểm ttra model tồn tại và ở trạng thái READY
        2. Archive model đang đưuọc deploy(nếu có)
        3. Chuyển model mới sang trạng thái DEPLOYED
        4. Đồng bộ trạng thái với MLflow Model Resgistry
        """
        # Lấy thông tin mode từ database
        model = await self.session.get(MLModel, model_id)
        if not model:
            raise ValueError(f"Model {model_id} không tồn tại")
        # Chỉ cho phép deloy model đã sẵn sàng
        if model.status != ModelStatusEnum.READY:
            raise ValueError(f"Model {model_id} chưa sẵn sàng để triển khai. (status: {model.status})")
        try:
            # Tìm model hiện đang được deploy
            stmt = select(MLModel).where(MLModel.status == ModelStatusEnum.READY)
            result = await self.session.exec(stmt)
            current_deploy = result.first()
            # Nếu đã có model đang chạy production
            if current_deploy:
                # Chuyển model cũ sang ARCHIVED
                current_deploy.status = ModelStatusEnum.ARCHIVED
                self.session.add(current_deploy)
                # Log trạng thái lên MLflow
                if current_deploy.mlflow_run_id:
                    try: 
                        with mlflow.start_run(run_id=current_deploy.mlflow_run_id):
                            mlflow.log_param("deploy_status", "ARCHIVED")
                            mlflow.log_param("archived_at", datetime.now(timezone.utc).isoformat())
                    except Exception as e:
                        logger.warning("Không thể cập nhật trạng thái MLflow cho mô hình đã lưu trữ: " f"{e}")
            # Deploy model mới
            model.status = ModelStatusEnum.DEPLOYED
            model.deployed_at = datetime.now(timezone.utc)
            self.session.add(model)
            # Log trạng thái deploy lên MLflow
            if model.mlflow_run_id:
                try:
                    with mlflow.start_run(run_id=model.mlflow_run_id):
                            mlflow.log_param("deploy_status", "ARCHIVED")
                            mlflow.log_param("deploy_at", model.deployed_at.isoformat())
                            # Đồng bộ với MLflow Model Registry
                            if model.mlflow_model_uri:
                                model_name = "fraud_detection_gradient_boosting"
                                client = mlflow.MlflowClient()
                                # Lấy version mới nhất của model trong registry
                                versions = client.get_latest_versions(model_name)
                                if versions:
                                    # Chọn version mới nhất (vừa được train)
                                    latest_version = versions[0].version
                                    # Chuyển version này sang stage Production
                                    client.transition_model_version_stage(name=model_name, version=latest_version, stage="Production")
                                    logger.info(f"Đã chuyển mô hình {model_name} phiên bản {latest_version} sang môi trường Production.")
                except Exception as e:
                    logger.warning(f"Không thể cập nhật trạng thái MLflow cho mô hình đã triển khai: {e}")
            # Commit thay đổi trạng thái vào database
            await self.session.commit()
            await self.session.refresh(model)
            logger.info(f"Đã triển khai mô hình {model.name} (phiên bản {model.version}) lên môi trường Production.")
            return model
        except Exception as e:
            logger.error(f"Lỗi triển khai mô hình: {e}")
            await self.session.rollback()
            raise

    async def get_deployed_model(self) -> Optional[MLModel]:
        """Lấy mô hình ML hiện đang được đeploy (Production)"""
        # Truy vấn model đang ở trạng thái DEPLOY
        stmt = select(MLModel).where(MLModel.status == ModelStatusEnum.DEPLOYED)
        result = await self.session.exec(stmt)
        return result.first()
                                
class ModelInference:
    def __init__(self, session: AsyncSession):
        """
        Khởi tạo service suy luận (inference) mô hình ML.
        Trách nhiệm:
        - Lưu database session để truy xuất thông tin model và dữ liệu liên quan
        - Khởi tạo bộ nhớ đệm model nhằm tối ưu hiệu năng suy luận
        - Thiết lập MLflow Tracking URI để tải và sử dụng model từ Model Registry
        """
        self.session = session
        self.model_cache = {}
        # Thiết lập MLflow Tracking Server cho all luồng inference
        mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)
    async def predict_fraud(self, transaction: Transaction) -> Tuple[float, Dict[str, Any]]:
        """
        Thực hiện suy luận (inference)  để dự đoán xác suất gian lận cho một giao dịch
        Quy trình:
        - Lấy model ML đang được deploy từ Model Registry
        - Trích xuất feature từ giao dịch 
        - Load model từ Mlflow (có cache để tối ưu)
        - Thực hiện dự đoán xác suất gian lận
        - Ghi nhận kết quả dựu đoán và log thông tin vào MLflow
        - Lưu kết quả prediction(dự đoán) vào CSDL 
        """
        try:
            # Service quản lý model đang được deploy
            deployer = ModelDeployer(self.session)
            # Lấy model hiện đang ở trạng thái production
            model_record = await deployer.get_deployed_model()
            # Không có model deploy -> fallback
            if not model_record:
                logger.warning("Không tìm thấy mô hình đã triển khai, sử dụng cơ chế dự đoán dự phòng (fallback).")
                return await self._fallback_prediction(transaction)
            # Model không có Mlflow URI -> fallback:
            if not model_record.mlflow_model_uri:
                logger.warning(f"Mô hình {model_record.id} không có MLflow URI, sử dụng cơ chế dự đoán dự phòng.")
                return await self._fallback_prediction(transaction)
            # Import tại runtime để tránh circular dependency
            from backend.app.core.ml.feature_engineering import FeatureExtractor
            # Trích xuất feature phục vụ suy luận
            feature_extractor = FeatureExtractor(self.session)
            features = await feature_extractor.extract_features_for_transaction(transaction)# Trích xuất giao dịch
            try:
                # Load Model từ cache nếu đã tồn tại
                if model_record.id not in self.model_cache:
                    model = load_model(model_record.mlflow_model_uri)
                    self.model_cache[model_record.id] = model
                else:
                    model = self.model_cache[model_record.id]
                # Kiểm tra model được load thành công
                if model is None:
                    logger.warning(f"Mô hình không thể được tải từ {model_record.mlflow_model_uri}")
                    return await self._fallback_prediction(transaction)
                # Loại bỏ field không phải feature đầu vào
                if "transaction_id" in features:
                    del features["transaction_id"]
                import pandas as pd
                # Chuyển feature dict sang DataFrame
                feature_df = pd.DataFrame([features])
                # Bổ sung các feature bị thiếu so với model đã train
                missing_cols = set(model.feature_names_in_) - set(feature_df.columns)
                for col in missing_cols:
                    feature_df[col] = 0
                # Đảm bảo đúng thứ tự feature 
                feature_df = feature_df[model.feature_names_in_]
                # Dự đoán xác suất gian lận
                fraud_probability = float(model.predict_proba(feature_df)[0, 1])
                # Phân tích mức độ đóng góp của từng feature vào kết quả dự đoán (nếu model hỗ trợ)
                feature_importance = {}
                # Chỉ áp dụng với các model có thuộc tính feature_importances_ (ví dụ: tree-based)
                if hasattr(model, "feature_importances_"):
                    importance_values = model.feature_importances_
                    for i, feature_name in enumerate(model.feature_names_in_):
                        if i < len(importance_values):
                            # Trọng số quan trọng của feature trong mô hình
                            importance = float(importance_values[i])
                            # Giá trị thực tế của feature trong giao dịch hiện tại
                            feature_value = float(feature_df[feature_name].iloc[0])
                            # Mức dóng góp xấp xỉ của feature vào prediction
                            contribution = importance * feature_value
                            # Chỉ giữ các feature có ảnh hưởng dương
                            if contribution > 0:
                                feature_importance[feature_name] = contribution
                # Lấy top 10 feature có ảnh hưởng lớn nhất
                top_features = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[10])
            except Exception as e:
                # Lỗi trong quá trình load hoặc suy luận model
                logger.error(f"Lỗi khi tải hoặc sử dụng mô hình MLflow: {e}.")
                return await self._fallback_prediction(transaction)
            # Log thông tin prediction vào MLflow run(nếu có)
            if model_record.mlflow_run_id:
                try:
                    # Gán vào MLflow run đã được tạo trong quá trình train/deploy
                    with mlflow.start_run(run_id=model_record.mlflow_run_id):
                        # Đém số lần model được sự dụng dể dự đoán
                        mlflow.log_metric("predictin_count", 1, step=1)
                        # Ghi lại điểm rủi ro (xác suất gian lận) của giao dịch
                        mlflow.log_metric("prediction_score", fraud_probability)
                        # Lưu tham chiếu giao dịch để phục vụ truy vết(audit)
                        mlflow.log_param("transaction_id", str(transaction.id))
                except Exception as e:
                    logger.warning(f"Không thể ghi (log) kết quả dự đoán lên MLflow: {e}.")
            # Lưu kết quả prediction vào CSDL
            prediction = ModelPrediction(
                transaction_id=transaction.id,
                model_id=model_record.id,
                prediction_score=fraud_probability,
                input_features=features,
                mlflow_run_id=model_record.mlflow_run_id
            )
            self.session.add(prediction)
            await self.session.commit()
            await self.session.refresh(prediction)
            # Thông tin chi tiết trả về cho tầng nghiệp vụ / API
            prediction_details = {
                "model_name": model_record.name,
                "model_version": model_record.version,
                "model_id": str(model_record.id),
                "prediction_time": datetime.now(timezone.utc).isoformat(),
                "mlflow_run_id": model_record.mlflow_run_id,
                "risk_factors": top_features,
            }
            return fraud_probability, prediction_details
        except Exception as e:
            logger.error(f"Lỗi trong quá trình dự đoán gian lận: {e}.")
            return await self._fallback_prediction(transaction)
    async def _fallback_prediction(self, transaction: Transaction) -> Tuple[float, Dict[str, Any]]:
        """
        Thực hiện dự đoán gian lận theo luật heuristic khi không thể sử dụng model ML.
        Nguyên tắc:
        - Đánh giá rủi ro dựa trên số tiền giao dịch
        - Điều chỉnh rủi ro theo thời gian thực hiện giao dịch
        - Trả về kết quả đơn giản, an toàn để đảm bảo hệ thống không bị gián đoạn
        """           
        # Giá trị tiền giao dịch
        amount = float(transaction.amount)
        # Ứng lượng xác suất gian lận dựa trên ngưỡng số tiền 
        if amount > 10000:
            fraud_probability = 0.7
        elif amount > 5000:
            fraud_probability = 0.5
        elif amount > 1000:
            fraud_probability = 0.3
        else:
            fraud_probability = 0.1
        # Lưu các yếu tố rủi ro dùng cho giải thích kết quả
        risk_factors = {"amount": amount}
        # Giờ thực hiện giao dịch 
        hour = transaction.created_at.hour
        # Kiểm tra giao dịch có nằm trong giờ hành chính hay không 
        is_business_hours = 9 <= hour <= 17
        risk_factors["outside_business_hours"] = 0 if is_business_hours else 0.2
        # Giao dịch đêm khuya có mức độ rủi do cao hơn
        if hour < 6 or hour > 22:
            fraud_probability += 0.1
            risk_factors["late_night_transaction"] =0.1
        # Giới hạn xác suất gian lận tối đa để tránh extreme value
        fraud_probability = min(0.9, fraud_probability)
        return fraud_probability, {
            "model_name": "fallback_heuristic",
            "model_version": "v1",
            "prediction_time": datetime.now(timezone.utc).isoformat(),
            "is_fallback": True,
            "risk_factors": risk_factors,
        }
async def update_transaction_risk(
    transaction: Transaction,
    fraud_probability: float,
    risk_threshold: float,
    prediction_details: Dict[str, Any],
    session: AsyncSession,
) -> Transaction:
    """
    Cập nhật kết quả đánh giá rủi ro giao dịch dựa trên xác suất gian lận
    Chức năng:
    - Ghi nhận thông tin đánh giá rủi ro vào metadata giao dịch
    - Xác định trạng thái giao dịch (FLAGGED/ CLEARED)
    - Lưu thay đổi vào CSDL 
    """
    # Khởi tạo metadata nếu chưa tồn tại
    if transaction.transaction_metadata is None:
        transaction.transaction_metadata = {}
    # Lưu kết quả đánh giá rủi ro của AI
    transaction.transaction_metadata["risk_assessment"] ={
        # Điểm rủi ro (xác suất gian lận) do hệ thống AI tính toán
        "score": fraud_probability, 
        # Ngưỡng rủi ro dùng để phân loại giao dịch
        "threshold": risk_threshold,
        # Đánh dấu giao dịch có vượt ngưỡng rủi ro không 
        "is_high_risk": fraud_probability >= risk_threshold,
        # Thời điểm thực hiện đánh giá rủi ro
        "assessment_at": datetime.now(timezone.utc).isoformat(),
        # Thông tin model dùng để dự đoán
        "model_details": {
            "name": prediction_details.get("model_name", "unknown"),
            "version":prediction_details.get("model_version", "unknown"),
            "id": prediction_details.get("model_id", "unknown"),
            "mlflow_run_id": prediction_details.get("mlflow_run_id", None)
        }
    }
    # Giao dịch vượt ngưỡng rủi ro -> cần kiểm tra thủ công
    if fraud_probability >= risk_threshold:
        transaction.ai_review_status = AIReviewStatusEnum.FLAGGED
        # Giữ nguyên trạng thái Pending để chờ xử lý tiếp
        if transaction.status == TransactionStatusEnum.Pending:
            transaction.ai_review_status = AIReviewStatusEnum.PENDING
    else:
        # Giao dịch an toàn theo đánh giá của AI
        transaction.ai_review_status = AIReviewStatusEnum.CLEARED
    # Lưu thay đổi vào CSDL
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction

        
        