from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import mlflow
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.ai.enums import AIReviewStatusEnum
from backend.app.core.logging import get_logger
from backend.app.core.ml.config import ml_settings
from backend.app.core.ml.models import MLModel, ModelPrediction
from backend.app.transaction.models import Transaction

logger = get_logger()

mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)

class ModelEvaluator:
    """
    Service đánh giá và so sánh hiệu năng các mô hình Machine Learning.
    Chịu trách nhiệm:
    - Kết nối với database (nếu cần lưu kết quả)
    - Quản lý MLflow experiment dùng cho việc so sánh model
    """
    def __init__(self, session: AsyncSession):
        # Session database dùng cho các thao tác lưu / truy vấn kết quả đánh giá
        self.session = session
        # Thiết lập MLflow experiment dùng để so sánh các mô hình
        try:
            # Thử lấy experiment đã tồn tại theo tên
            experiment = mlflow.get_experiment_by_name("model_comparisons")
            if experiment:
                # Nếu đã tồn tại thì dùng lại experiment_id
                self.experiment_id = experiment.experiment_id
            else:
                # Nếu chưa tồn tại thì tạo experiment mới
                self.experiment_id = mlflow.create_experiment(
                    "model_comparisons"
                )
        except Exception as e:
            # Trường hợp MLflow lỗi
            logger.error(f"Failed to setup MLflow experiment: {e}")
            self.experiment_id = None
    async def _calculate_auc(self, predictions, actuals):
        """
        Tính AUC (Area Under ROC Curve) cho mô hình.

        AUC đo lường khả năng mô hình phân biệt giữa:
        - Giao dịch gian lận (positive)
        - Giao dịch hợp lệ (negative)

        Giá trị:
        - 0.5  : mô hình đoán ngẫu nhiên
        - 1.0  : phân biệt hoàn hảo
        """
        try:
            # Ưu tiên dùng sklearn nếu có
            from sklearn.metrics import roc_auc_score

            # AUC không xác định nếu chỉ có 1 class
            if len(set(actuals)) < 2:
                logger.warning("cannot calculate the AUC with less than 2 classes")
                return 0.5

            return float(roc_auc_score(actuals, predictions))

        except ImportError:
            # Fallback: tính AUC thủ công nếu không có sklearn
            logger.warning(
                "scikit-learn not available, using approximate AUC calculation"
            )

            # Số lượng mẫu positive và negative
            n_pos = sum(actuals)
            n_neg = len(actuals) - n_pos

            # Nếu không có đủ cả hai class → AUC mặc định
            if n_pos == 0 or n_neg == 0:
                return 0.5

            # Ghép prediction với label, sắp xếp theo score giảm dần
            paired = sorted(
                zip(predictions, actuals),
                key=lambda x: x[0],
                reverse=True,
            )

            # Lấy thứ hạng (rank) của các mẫu positive
            ranks = [i + 1 for i in range(len(paired)) if paired[i][1] == 1]

            # Công thức AUC dựa trên Mann–Whitney U statistic
            return (sum(ranks) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


    async def _calculate_recall(self, predictions, actuals):
        """
        Tính Recall (Sensitivity).

        Recall đo lường:
        - Trong tất cả giao dịch gian lận thật sự
        - Mô hình phát hiện được bao nhiêu

        Công thức:
        Recall = TP / (TP + FN)
        """

        # Đếm số true positive với ngưỡng 0.5
        true_positives = sum(
            1 for p, a in zip(predictions, actuals) if p >= 0.5 and a == 1
        )

        # Tổng số giao dịch gian lận thật
        actual_positives = sum(actuals)

        # Tránh chia cho 0
        if actual_positives == 0:
            return 0.0

        return true_positives / actual_positives


    async def _calculate_f1(self, predictions, actuals):
        """
        Tính F1-score.

        F1 là trung bình điều hoà giữa Precision và Recall,
        thường dùng trong fraud detection do dữ liệu mất cân bằng.

        Công thức:
        F1 = 2 * (Precision * Recall) / (Precision + Recall)
        """

        precision = await self._calculate_precision(predictions, actuals)
        recall = await self._calculate_recall(predictions, actuals)

        # Tránh chia cho 0
        if precision + recall == 0:
            return 0.0

        return 2 * precision * recall / (precision + recall)
    async def _calculate_precision(self, predictions, actuals):
        """
        Tính Precision (độ chính xác của dự đoán gian lận).
        Precision đo lường:
        - Trong các giao dịch mà mô hình dự đoán là gian lận
        - Có bao nhiêu giao dịch thực sự là gian lận
        Công thức:
        Precision = TP / (TP + FP)
        Precision cao giúp:
        - Giảm false positive
        - Tránh chặn nhầm giao dịch hợp lệ
        """
        # Tổng số giao dịch được mô hình dự đoán là gian lận
        # Dựa trên ngưỡng phân loại mặc định 0.5
        predicted_positive = sum(
            1 for p in predictions if p >= 0.5
        )

        # Nếu mô hình không dự đoán gian lận nào → precision = 0
        if predicted_positive == 0:
            return 0.0

        # Đếm số giao dịch vừa được dự đoán là gian lận
        # vừa thực sự là gian lận (true positive)
        true_positives = sum(
            1 for p, a in zip(predictions, actuals)
            if p >= 0.5 and a == 1
        )

        return true_positives / predicted_positive

    async def _generate_confusion_matrix(self, predictions, actuals):
        """
        Sinh confusion matrix cho mô hình phân loại gian lận.
        Confusion matrix gồm 4 thành phần:
        - True Positive  (TP): dự đoán fraud & thực sự fraud
        - False Positive (FP): dự đoán fraud nhưng thực tế hợp lệ
        - True Negative  (TN): dự đoán hợp lệ & thực tế hợp lệ
        - False Negative (FN): dự đoán hợp lệ nhưng thực tế fraud
        Ngưỡng phân loại mặc định: 0.5
        """
        return {
            # Dự đoán >= 0.5 và thực tế là fraud
            "true_positives": sum(
                1 for p, a in zip(predictions, actuals) if p >= 0.5 and a == 1
            ),
            # Dự đoán >= 0.5 nhưng thực tế không fraud (chặn nhầm)
            "false_positives": sum(
                1 for p, a in zip(predictions, actuals) if p >= 0.5 and a == 0
            ),
            # Dự đoán < 0.5 và thực tế không fraud
            "true_negatives": sum(
                1 for p, a in zip(predictions, actuals) if p < 0.5 and a == 0
            ),
            # Dự đoán < 0.5 nhưng thực tế fraud (bỏ sót gian lận)
            "false_negatives": sum(
                1 for p, a in zip(predictions, actuals) if p < 0.5 and a == 1
            ),
        }
    async def evaluate_model_performance(
        self,
        model_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Đánh giá hiệu năng của một mô hình ML trong một khoảng thời gian.
        Quy trình:
        1. Lấy thông tin model
        2. Xác định khoảng thời gian đánh giá
        3. Lấy toàn bộ prediction của model
        4. Ghép prediction với nhãn thực tế
        5. Tính các metric đánh giá
        6. Log kết quả lên MLflow
        """
        try:
            # Lấy thông tin model từ database
            model = await self.session.get(MLModel, model_id)

            if not model:
                raise ValueError(f"Model {model_id} not found")

            # Nếu không truyền thời gian → mặc định đánh giá 30 ngày gần nhất
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Log khoảng thời gian đánh giá vào MLflow để audit
            if model.mlflow_run_id:
                with mlflow.start_run(run_id=model.mlflow_run_id):
                    mlflow.log_param("evaluation_start_date", start_date.isoformat())
                    mlflow.log_param("evaluation_end_date", end_date.isoformat())

            # Lấy toàn bộ prediction của model trong khoảng thời gian đánh giá
            query = select(ModelPrediction).where(
                ModelPrediction.model_id == model_id,
                ModelPrediction.prediction_timestamp >= start_date,
                ModelPrediction.prediction_timestamp <= end_date,
            )

            result = await self.session.exec(query)
            predictions = result.all()

            transaction_ids = [p.transaction_id for p in predictions]

            # Trường hợp model chưa có prediction nào
            if not transaction_ids:
                logger.warning(
                    f"No predictions found for model {model_id} in the specified time period"
                )
                return {
                    "model_id": str(model_id),
                    "model_name": model.name,
                    "model_version": model.version,
                    "evaluation_period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    },
                    "metrics": {
                        "total_predictions": 0,
                        "error": "No predictions found in the specified time period",
                    },
                }

            # Lấy thông tin transaction tương ứng để xác định nhãn thực tế
            transactions = []

            for tx_id in transaction_ids:
                tx_query = select(Transaction).where(Transaction.id == tx_id)
                tx_result = await self.session.exec(tx_query)
                tx = tx_result.first()
                if tx:
                    transactions.append(tx)

            # Map transaction_id → nhãn thực tế (fraud hay không)
            transaction_status_map = {
                t.id: (t.ai_review_status == AIReviewStatusEnum.FLAGGED)
                for t in transactions
            }

            # Danh sách score dự đoán
            prediction_scores = [
                p.prediction_score
                for p in predictions
                if p.transaction_id in transaction_status_map
            ]

            # Danh sách nhãn thực tế (0/1)
            actual_labels = [
                1 if transaction_status_map.get(p.transaction_id, False) else 0
                for p in predictions
                if p.transaction_id in transaction_status_map
            ]

            # Tính các metric đánh giá mô hình
            metrics = {
                "auc": await self._calculate_auc(prediction_scores, actual_labels),
                "precision": await self._calculate_precision(
                    prediction_scores, actual_labels
                ),
                "recall": await self._calculate_recall(
                    prediction_scores, actual_labels
                ),
                "f1": await self._calculate_f1(prediction_scores, actual_labels),

                # Tổng số prediction được đánh giá
                "total_preidictions": len(predictions),

                # Confusion matrix để phân tích lỗi
                "confusion_matrix": await self._generate_confusion_matrix(
                    prediction_scores, actual_labels
                ),
            }

            # Log metric & artifact lên MLflow
            if model.mlflow_run_id:
                with mlflow.start_run(run_id=model.mlflow_run_id):
                    for metric_name, metric_value in metrics.items():
                        if isinstance(metric_value, (int, float)):
                            mlflow.log_metric(f"eval_{metric_name}", metric_value)

                    # Lưu confusion matrix dưới dạng artifact
                    if "confusion_matrix" in metrics:
                        import json

                        cm_path = "/tmp/confusion_matrix.json"
                        with open(cm_path, "w") as f:
                            json.dump(metrics["confusion_matrix"], f)

                        mlflow.log_artifact(cm_path, "evaluation")

            # Trả kết quả đánh giá
            return {
                "model_id": str(model_id),
                "model_name": model.name,
                "model_version": model.version,
                "evaluation_period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "metrics": metrics,
            }

        except Exception as e:
            logger.error(f"Error evaluating model performance: {e}")
            raise
    async def get_model_metrics_trend(
        self, model_id: UUID, days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Lấy xu hướng (trend) các metric đánh giá mô hình theo từng ngày.
        Mục đích:
        - Theo dõi hiệu năng model theo thời gian
        - Phát hiện model bị drift hoặc suy giảm chất lượng
        - Phục vụ dashboard, monitoring, alert
        """
        # Ngày kết thúc: hiện tại
        end_date = datetime.now(timezone.utc)

        # Ngày bắt đầu: lùi về `days` ngày
        start_date = end_date - timedelta(days=days)

        metrics_trend: List[Dict[str, Any]] = []

        current_date = start_date

        # Duyệt từng ngày trong khoảng thời gian
        while current_date <= end_date:
            # Xác định đầu ngày (00:00:00)
            day_start = current_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Xác định cuối ngày (23:59:59.999999)
            day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)

            try:
                # Đánh giá model trong đúng 1 ngày
                daily_metrics = await self.evaluate_model_performance(
                    model_id=model_id,
                    start_date=day_start,
                    end_date=day_end,
                )

                # Chỉ ghi nhận ngày có prediction
                if daily_metrics["metrics"]["total_predictions"] > 0:
                    metrics_trend.append(
                        {
                            "date": day_start.strftime("%Y-%m-%d"),
                            "metrics": daily_metrics["metrics"],
                        }
                    )

            except Exception as e:
                # Không để lỗi một ngày làm hỏng toàn bộ chuỗi trend
                logger.error(
                    f"Error getting metrics for {day_start.date()}: {e}"
                )

            # Sang ngày tiếp theo
            current_date += timedelta(days=1)

        return metrics_trend
    async def get_false_positives(
        self,
        model_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các giao dịch bị model dự đoán là gian lận
        nhưng thực tế được xác nhận là hợp lệ (False Positives).
        Mục đích:
        - Phân tích lỗi model
        - Giảm chặn nhầm khách hàng
        - Phục vụ cải tiến feature và tuning threshold
        """
        # Mặc định đánh giá 30 ngày gần nhất
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Truy vấn các prediction có:
        # - score >= 0.5 (model cho là fraud)
        # - nhưng transaction đã được xác nhận CLEARED (không gian lận)
        stmt = (
            select(ModelPrediction, Transaction)
            .join(Transaction)
            .where(
                ModelPrediction.transaction_id == Transaction.id,
                ModelPrediction.model_id == model_id,
                ModelPrediction.prediction_timestamp >= start_date,
                ModelPrediction.prediction_timestamp <= end_date,
                ModelPrediction.prediction_score >= 0.5,
                Transaction.ai_review_status == AIReviewStatusEnum.CLEARED,
            )
            # Ưu tiên các case score cao nhất (nghiêm trọng nhất)
            .order_by(desc(ModelPrediction.prediction_score))
            .limit(limit)
        )

        result = await self.session.exec(stmt)
        false_positives = result.all()
        # Tạo mảng
        formatted_results: List[Dict[str, Any]] = []

        # Chuẩn hoá dữ liệu trả về
        for prediction, tx in false_positives:
            formatted_results.append(
                {
                    "transaction_id": str(tx.id),
                    "reference": tx.reference,
                    "amount": str(tx.amount),
                    "prediction_score": prediction.prediction_score,
                    "transaction_date": tx.created_at.isoformat(),
                    "prediction_date": prediction.prediction_timestamp.isoformat(),
                    "features": prediction.input_features,
                    "metadata": tx.transaction_metadata,
                }
            )

        # Log thông tin false positive lên MLflow để audit
        model = await self.session.get(MLModel, model_id)

        if model and model.mlflow_run_id and formatted_results:
            with mlflow.start_run(run_id=model.mlflow_run_id):
                # Log tổng số false positive
                mlflow.log_metric(
                    "false_positive_count",
                    len(formatted_results),
                )

                # Log score của top false positive (nghiêm trọng nhất)
                for i, fp in enumerate(formatted_results[:5]):
                    mlflow.log_metric(
                        f"top_fp_{i+1}_score",
                        fp["prediction_score"],
                    )

                # Lưu danh sách false positive làm artifact
                import json

                fp_path = "/tmp/false_positives.json"

                with open(fp_path, "w") as f:
                    json.dump(formatted_results, f)

                mlflow.log_artifact(fp_path, "evaluation/false_positives")

        return formatted_results
    async def get_false_negatives(
        self,
        model_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các giao dịch gian lận thật sự
        nhưng mô hình KHÔNG phát hiện được (False Negatives).

        False Negative là lỗi nghiêm trọng nhất trong fraud detection
        vì:
        - Gian lận lọt qua hệ thống
        - Gây thiệt hại tài chính trực tiếp
        """

        # Mặc định phân tích 30 ngày gần nhất
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Truy vấn các prediction có:
        # - score < 0.5 (model cho là an toàn)
        # - nhưng đã được xác nhận gian lận (CONFIRMED_FRAUD)
        stmt = (
            select(ModelPrediction, Transaction)
            .join(Transaction)
            .where(
                ModelPrediction.transaction_id == Transaction.id,
                ModelPrediction.model_id == model_id,
                ModelPrediction.prediction_timestamp >= start_date,
                ModelPrediction.prediction_timestamp <= end_date,
                ModelPrediction.prediction_score < 0.5,
                Transaction.ai_review_status == AIReviewStatusEnum.CONFIRMED_FRAUD,
            )
            # Ưu tiên các case có score cao nhất
            # (model suýt nữa đã phát hiện)
            .order_by(desc(ModelPrediction.prediction_score))
            .limit(limit)
        )

        result = await self.session.exec(stmt)
        false_negatives = result.all()

        formatted_results: List[Dict[str, Any]] = []

        # Chuẩn hoá dữ liệu trả về để phục vụ phân tích
        for prediction, tx in false_negatives:
            formatted_results.append(
                {
                    "transaction_id": str(tx.id),
                    "reference": tx.reference,
                    "amount": str(tx.amount),
                    "prediction_score": prediction.prediction_score,
                    "transaction_date": tx.created_at.isoformat(),
                    "prediction_date": prediction.prediction_timestamp.isoformat(),
                    "features": prediction.input_features,
                    "metadata": tx.transaction_metadata,
                }
            )

        # Log thông tin false negative lên MLflow để audit & cải tiến model
        model = await self.session.get(MLModel, model_id)

        if model and model.mlflow_run_id and formatted_results:
            with mlflow.start_run(run_id=model.mlflow_run_id):
                # Tổng số false negative
                mlflow.log_metric(
                    "false_negative_count",
                    len(formatted_results),
                )

                # Log score của các false negative nguy hiểm nhất
                for i, fn in enumerate(formatted_results[:5]):
                    mlflow.log_metric(
                        f"top_fn_{i+1}_score",
                        fn["prediction_score"],
                    )

                # Lưu chi tiết false negative để phân tích offline
                import json

                fn_path = "/tmp/false_negatives.json"

                with open(fn_path, "w") as f:
                    json.dump(formatted_results, f)

                mlflow.log_artifact(fn_path, "evaluation/false_negatives")

        return formatted_results
    async def compare_models(
        self,
        model_ids: List[UUID],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        So sánh hiệu năng của nhiều mô hình Machine Learning
        trong cùng một khoảng thời gian.

        Chức năng:
        - Đánh giá từng model theo cùng tập dữ liệu
        - So sánh các metric chính (AUC, Precision, Recall, F1)
        - Log kết quả và biểu đồ so sánh lên MLflow
        """
        # Lưu mertic của từng model
        models_metrics: Dict[str, Any] = {}
        # Mở một MLflow run dùng riêng cho việc so sánh model
        with mlflow.start_run(
            experiment_id=self.experiment_id,
            run_name="model_comparison"
        ) as run:
            comparison_run_id = run.info.run_id
            # Log metadata của lần so sánh
            mlflow.log_param(
                "comparison_date",
                datetime.now(timezone.utc).isoformat()
            )
            mlflow.log_param(
                "models_compared",
                len(model_ids)
            )
            # Đánh giá lần lượt từng model
            for model_id in model_ids:
                try:
                    # Đánh giá hiệu năng model
                    metrics = await self.evaluate_model_performance(
                        model_id=model_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                    # Lưu kết quả để trả về API
                    models_metrics[str(model_id)] = {
                        "name": metrics["model_name"],
                        "version": metrics["model_version"],
                        "metrics": metrics["metrics"]
                    }
                    # Log metric chính lên MLflow
                    mlflow.log_metrics(
                        {
                            f"model_{model_id}_auc": metrics["metrics"]["auc"],
                            f"model_{model_id}_precision": metrics["metrics"]["precision"],
                            f"model_{model_id}_recall": metrics["metrics"]["recall"],
                            f"model_{model_id}_f1": metrics["metrics"]["f1"],
                        }
                    )
                except Exception as e:
                    # Không để lỗi 1 model làm hỏng toàn bộ quá trình so sánh
                    logger.error(f"Error evaluating model {model_id}: {e}")
                    models_metrics[str(model_id)] = {"error": str(e)}
            # Nếu có từ 2 model trở lên → tạo biểu đồ so sánh
            if len(models_metrics) > 1:
                try:
                    import matplotlib.pyplot as plt
                    import numpy as np

                    # Các metric cần so sánh
                    metrics_to_plot = ["auc", "precision", "recall", "f1"]

                    # Tên model hiển thị trên biểu đồ
                    model_names = [
                        m["name"] + " " + m["version"]
                        for m in models_metrics.values()
                        if "error" not in m
                    ]

                    plt.figure(figsize=(10, 6))

                    x = np.arange(len(metrics_to_plot))

                    # Độ rộng mỗi cột
                    width = 0.8 / len(model_names)

                    # Vẽ cột cho từng model
                    for i, (model_id, model_data) in enumerate(models_metrics.items()):
                        if "error" not in model_data:
                            values = [
                                model_data["metrics"].get(m, 0)
                                for m in metrics_to_plot
                            ]
                            plt.bar(
                                x + i * width,
                                values,
                                width,
                                label=model_data["name"]
                                + " "
                                + model_data["version"],
                            )

                    plt.ylabel("Score")
                    plt.title("Model Performance Comparison")
                    plt.xticks(x + width / 2, metrics_to_plot)
                    plt.legend()
                    plt.tight_layout()

                    # Lưu biểu đồ và log lên MLflow
                    comparison_plot_path = "/tmp/model_comparison.png"
                    plt.savefig(comparison_plot_path)

                    mlflow.log_artifact(
                        comparison_plot_path,
                        "evaluation/comparison",
                    )

                except Exception as e:
                    # Visualization lỗi cũng không làm hỏng kết quả so sánh
                    logger.error(
                        f"Error creating comparison visualization: {e}"
                    )

        # Trả kết quả so sánh cho API / dashboard
        return {
            "comparison_run_id": comparison_run_id,
            "comparison_period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "models": models_metrics,
        }