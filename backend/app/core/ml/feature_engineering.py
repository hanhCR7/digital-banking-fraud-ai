from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import mlflow
import numpy as np
import pandas as pd
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.bank_account.models import BankAccount
from backend.app.core.ai.models import TransactionRiskScore
from backend.app.core.logging import get_logger
from backend.app.transaction.models import Transaction

logger = get_logger()


class FeatureExtractor:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.feature_names = []
    
    def _extract_time_features(self, transaction: Transaction) -> dict[str, Any]:
        """
        Trích xuất các đặc trưng thời gian của giao dịch để phục vụ phân tích rủi ro.

        Bao gồm: giờ giao dịch, thứ trong tuần, cuối tuần, giờ hành chính,
        giao dịch đêm khuya, đầu tháng và cuối tháng.
        """
        created_at = transaction.created_at

        is_banking_hours = 1 if 9 <= created_at.hour <= 17 else 0
        is_late_night = 1 if created_at.hour <= 5 or created_at.hour >= 23 else 0 # Đêm khuya

        month = created_at.month
        day = created_at.day
        day_of_week = created_at.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0 # Cuối tuần

        is_month_end = 1 if day >= 25 else 0 # Đầu tháng
        is_month_start = 1 if day <= 5 else 0 # Cuối tháng

        return {
            "hour_of_day": created_at.hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_banking_hours": is_banking_hours,
            "is_late_night": is_late_night,
            "month": month,
            "day": day,
            "is_month_end": is_month_end,
            "is_month_start": is_month_start,
        }
    def _extract_metadata_features(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Trích xuất các đặc trưng từ metadata của giao dịch.

        Hàm này xử lý các thông tin bổ sung không nằm trong schema cố định
        của transaction, chủ yếu phục vụ phân tích rủi ro liên quan đến:
        - Loại tiền tệ sử dụng
        - Giao dịch có đổi tiền hay không
        - Tỷ lệ chuyển đổi giữa các loại tiền

        Metadata thường được dùng cho các trường hợp đặc biệt như
        giao dịch quốc tế hoặc giao dịch có xử lý trung gian.
        """
        features = {}

        # Không có metadata thì không sinh thêm feature
        if not metadata:
            return features

        currency_value = None

        # Xác định loại tiền tệ chính của giao dịch
        if "currency" in metadata:
            currency_value = metadata["currency"]
        elif isinstance(metadata.get("from_currency"), str):
            currency_value = metadata["from_currency"]

        # One-hot encoding cho currency
        if currency_value:
            features["currency"] = currency_value
            features[f"currency_{currency_value}"] = 1

        # Kiểm tra giao dịch có phải là giao dịch đổi tiền hay không
        if "converted_amount" in metadata:
            features["is_currency_conversion"] = 1
            try:
                # Tính tỷ lệ chuyển đổi giữa số tiền gốc và số tiền sau khi đổi
                conversion_ratio = float(metadata.get("converted_amount", 0)) / float(
                    metadata.get("original_amount", 1)
                    or metadata.get("amount", 1)
                )
                features["conversion_ratio"] = conversion_ratio
            except (ValueError, ZeroDivisionError):
                # Trường hợp dữ liệu không hợp lệ hoặc chia cho 0
                features["conversion_ratio"] = 0
        else:
            features["is_currency_conversion"] = 0

        return features
    async def _extract_account_features(
        self, account_id: UUID, is_sender: bool
    ) -> dict[str, Any]:
        """
        Trích xuất các đặc trưng liên quan đến tài khoản tham gia giao dịch.

        Hàm này áp dụng cho cả tài khoản gửi (sender) và tài khoản nhận (receiver),
        nhằm phản ánh mức độ hoạt động, tuổi tài khoản và hành vi giao dịch lịch sử.
        Các đặc trưng này giúp mô hình phát hiện tài khoản mới, ít hoạt động
        hoặc có hành vi giao dịch bất thường.
        """
        # Xác định prefix để phân biệt sender và receiver
        prefix = "sender" if is_sender else "receiver"

        # Lấy thông tin tài khoản từ database
        account = await self.session.get(BankAccount, account_id)

        # Trường hợp không tìm thấy tài khoản (dữ liệu bất thường)
        if not account:
            return {f"{prefix}_account_not_found": 1}

        # Thông tin cơ bản của tài khoản
        features = {
            f"{prefix}_account_balance": float(account.balance),
            f"{prefix}_account_age_days": (
                datetime.now(account.created_at.tzinfo) - account.created_at
            ).days,
        }

        # Ghi nhận trạng thái tài khoản (active, blocked, ...)
        if hasattr(account, "account_status") and account.account_status:
            features[f"{prefix}_account_status_{account.account_status.value}"] = 1

        # Lấy lịch sử giao dịch của tài khoản
        if is_sender:
            stmt = select(Transaction).where(
                Transaction.sender_account_id == account_id
            )
        else:
            stmt = select(Transaction).where(
                Transaction.receiver_account_id == account_id
            )

        result = await self.session.exec(stmt)
        transactions = result.all()

        # Tổng số giao dịch của tài khoản
        features[f"{prefix}_transaction_count"] = len(transactions)

        if transactions:
            amounts = [float(t.amount) for t in transactions]

            # Thống kê số tiền giao dịch
            features[f"{prefix}_avg_transaction_amount"] = np.mean(amounts)
            # Nếu tài khoản có nhiều hơn một giao dịch, tính các thống kê để đo mức độ biến động số tiền
            if len(transactions) > 1:
                features[f"{prefix}_std_transaction_amount"] = float(np.std(amounts))# độ lệch chuẩn
                features[f"{prefix}_max_transaction_amount"] = float(np.max(amounts))
                features[f"{prefix}_min_transaction_amount"] = float(np.min(amounts))
            else:
                # Trường hợp chỉ có một giao dịch
                features[f"{prefix}_std_transaction_amount"] = 0.0
                features[f"{prefix}_max_transaction_amount"] = amounts[0]
                features[f"{prefix}_min_transaction_amount"] = amounts[0]

        return features
    async def _extract_user_history_features(
        self,
        user_id: UUID,
        current_time: datetime,
    ) -> dict[str, Any]:
        """
        Trích xuất các đặc trưng thống kê từ lịch sử giao dịch của người dùng
        trong 90 ngày gần nhất để phục vụ phân tích rủi ro / AI model.
        """

        # Xác định khoảng thời gian lookback (90 ngày)
        lookback_period = current_time - timedelta(days=90)

        # Truy vấn toàn bộ giao dịch của user trong khoảng thời gian này
        stmt = select(Transaction).where(
            Transaction.sender_id == user_id,
            Transaction.created_at >= lookback_period,
            Transaction.created_at < current_time,
        )

        result = await self.session.exec(stmt)
        transactions = result.all()

        # Nếu user chưa có giao dịch nào trong 90 ngày
        if not transactions:
            return {
                "user_transaction_count_90d": 0,
                "user_avg_amount_90d": 0,
                "user_max_amount_90d": 0,
                "user_transaction_frequency_daily": 0,
            }

        # Lấy danh sách số tiền giao dịch
        amounts = [float(t.amount) for t in transactions]

        # Tổng số ngày trong khoảng phân tích (tránh chia cho 0)
        days_in_history = (current_time - lookback_period).days or 1

        # Tần suất giao dịch trung bình mỗi ngày
        tx_per_day = len(transactions) / days_in_history

        # Các feature thống kê chính
        features: dict[str, Any] = {
            "user_transaction_count_90d": len(transactions),
            "user_avg_amount_90d": float(np.mean(amounts)) if amounts else 0,
            "user_max_amount_90d": float(np.max(amounts)) if amounts else 0,
            "user_min_amount_90d": float(np.min(amounts)) if amounts else 0,
            "user_std_amount_90d": float(np.std(amounts)) if len(amounts) > 1 else 0,
            "user_transaction_frequency_daily": tx_per_day,
        }

        # Phân bố tỷ lệ các loại giao dịch (transfer, withdraw, deposit, ...)
        tx_types = [t.transaction_type.value for t in transactions]

        for tx_type in set(tx_types):
            count = tx_types.count(tx_type)
            features[f"user_tx_type_{tx_type}_ratio"] = count / len(transactions)

        return features
    async def _extract_velocity_features(
        self,
        user_id: UUID,
        current_time: datetime,
    ) -> dict[str, Any]:
        """
        Trích xuất các feature về tốc độ giao dịch (velocity features)
        của người dùng trong nhiều cửa sổ thời gian khác nhau.

        Các feature này dùng để:
        - Phát hiện hành vi giao dịch dồn dập
        - Phát hiện gian lận theo thời gian ngắn
        """

        # Các cửa sổ thời gian cần phân tích
        time_windows = [
            ("1h", timedelta(hours=1)),
            ("1d", timedelta(days=1)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
        ]

        features: dict[str, Any] = {}

        for window_name, window_size in time_windows:
            # Xác định thời điểm bắt đầu của cửa sổ phân tích
            lookback_time = current_time - window_size

            # Lấy các giao dịch của user trong cửa sổ thời gian này
            stmt = select(Transaction).where(
                Transaction.sender_id == user_id,
                Transaction.created_at >= lookback_time,
                Transaction.created_at < current_time,
            )

            result = await self.session.exec(stmt)
            transactions = result.all()

            # Số lượng giao dịch trong cửa sổ thời gian
            features[f"tx_count_{window_name}"] = len(transactions)

            if transactions:
                # Tổng giá trị giao dịch trong cửa sổ
                total_amount = sum(float(t.amount) for t in transactions)
                features[f"tx_total_amount_{window_name}"] = total_amount

                # Giá trị giao dịch trung bình
                features[f"tx_avg_amount_{window_name}"] = (
                    total_amount / len(transactions)
                )
            else:
                # Không có giao dịch → set giá trị 0 để tránh None
                features[f"tx_total_amount_{window_name}"] = 0
                features[f"tx_avg_amount_{window_name}"] = 0

        return features
    async def extract_features_for_transaction(
        self,
        transaction: Transaction,
        mlflow_run_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Trích xuất feature cho một giao dịch cụ thể để phục vụ:
        - Phân tích rủi ro
        - Phát hiện gian lận
        - Huấn luyện / inference mô hình AI

        Hàm này gom feature từ nhiều nguồn:
        - Bản thân giao dịch
        - Thời gian giao dịch
        - Tài khoản liên quan
        - Lịch sử & velocity của người dùng
        - Metadata phát sinh trong giao dịch
        """
        try:
            # Feature cơ bản trực tiếp từ giao dịch
            features: dict[str, Any] = {
                "amount": float(transaction.amount),  # Số tiền giao dịch
                "transaction_type": transaction.transaction_type.value,  # Loại giao dịch
                "transaction_category": transaction.transaction_category.value,  # Nhóm giao dịch
            }

            # One-hot encoding cho loại và nhóm giao dịch
            # Giúp mô hình phân biệt transfer / withdraw / deposit...
            features[f"tx_type_{transaction.transaction_type.value}"] = 1
            features[f"tx_category_{transaction.transaction_category.value}"] = 1

            # Feature liên quan đến thời gian (giờ trong ngày, ngày trong tuần, ngoài giờ hành chính...)
            features.update(self._extract_time_features(transaction))

            # Feature của tài khoản người gửi
            # Thường phản ánh mức độ rủi ro cao hơn so với người nhận
            if transaction.sender_account_id:
                sender_account_features = await self._extract_account_features(
                    transaction.sender_account_id,
                    is_sender=True,
                )
                features.update(sender_account_features)

            # Feature của tài khoản người nhận
            # Dùng để phát hiện tài khoản đích bất thường
            if transaction.receiver_account_id:
                receiver_account_features = await self._extract_account_features(
                    transaction.receiver_account_id,
                    is_sender=False,
                )
                features.update(receiver_account_features)

            # Feature lịch sử giao dịch của user
            # Phản ánh hành vi dài hạn (90 ngày)
            if transaction.sender_id:
                user_history_features = await self._extract_user_history_features(
                    transaction.sender_id,
                    transaction.created_at,
                )
                features.update(user_history_features)

                # Feature velocity phản ánh hành vi ngắn hạn (1h, 1d, 7d, 30d)
                velocity_features = await self._extract_velocity_features(
                    transaction.sender_id,
                    transaction.created_at,
                )
                features.update(velocity_features)

            # Feature trích xuất từ metadata giao dịch
            # Ví dụ: chuyển đổi tiền tệ, phí, nguồn dữ liệu phụ trợ
            if transaction.transaction_metadata:
                metadata_features = self._extract_metadata_features(
                    transaction.transaction_metadata
                )
                features.update(metadata_features)

            # Ghi log thông tin feature lên MLflow để phục vụ debug và audit
            # Không ảnh hưởng tới luồng xử lý chính nếu MLflow lỗi
            if mlflow_run_id:
                tx_id_short = str(transaction.id)[-8:]
                try:
                    with mlflow.start_run(run_id=mlflow_run_id):
                        mlflow.log_metric(
                            f"tx_{tx_id_short}_feature_count",
                            len(features),
                        )
                        mlflow.log_metric(
                            f"tx_{tx_id_short}_amount",
                            features.get("amount", 0),
                        )
                        mlflow.log_metric(
                            f"tx_{tx_id_short}_hour",
                            features.get("hour_of_day", 0),
                        )
                        mlflow.log_param(
                            f"processed_tx_{tx_id_short}",
                            1,
                        )
                except Exception as mlflow_error:
                    logger.warning(
                        f"MLflow logging error for transaction {tx_id_short}: {mlflow_error}"
                    )

            return features

        except Exception as e:
            # Fail-safe: nếu quá trình trích xuất feature gặp lỗi
            # Trả về feature tối thiểu để tránh làm gián đoạn pipeline
            logger.error(f"Error extracting features: {e}")

            return {
                "amount": float(transaction.amount),
                "hour_of_day": transaction.created_at.hour,
                "day_of_week": transaction.created_at.weekday(),
                "error_in_feature_extraction": 1,
            }

async def prepare_training_dataset(
    session: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    mlflow_run_id: str | None = None,
) -> pd.DataFrame:
    """
    Chuẩn bị dataset huấn luyện cho mô hình phát hiện gian lận giao dịch.

    Hàm này chịu trách nhiệm:
    - Thu thập giao dịch trong khoảng thời gian xác định
    - Trích xuất feature cho từng giao dịch
    - Gán nhãn is_fraud dựa trên nhiều nguồn xác nhận
    - Chuẩn hoá dữ liệu để sẵn sàng đưa vào mô hình ML
    """

    # Ghi log khoảng thời gian tạo dataset để audit
    logger.info(f"Preparing training dataset from {start_date} to {end_date}")

    # Truy vấn toàn bộ giao dịch trong khoảng thời gian training
    stmt = select(Transaction).where(
        Transaction.created_at >= start_date,
        Transaction.created_at <= end_date,
    )

    result = await session.exec(stmt)
    transactions = result.all()

    # Log số lượng giao dịch tìm được
    logger.info(f"Found {len(transactions)} transactions for feature extraction")

    # Kiểm tra trạng thái MLflow hiện tại
    # Nếu đang có run khác nhưng user truyền run_id mới → kết thúc run cũ
    active_run = mlflow.active_run()
    if (
        mlflow_run_id
        and active_run is not None
        and active_run.info.run_id != mlflow_run_id
    ):
        logger.info("Ending existing MLflow run before starting a new one")
        mlflow.end_run()

    # Khởi tạo feature extractor (chịu trách nhiệm gom toàn bộ feature)
    feature_extractor = FeatureExtractor(session)

    # Danh sách lưu feature của từng giao dịch
    all_features: list[dict[str, Any]] = []

    # Duyệt từng giao dịch để trích xuất feature
    for tx in transactions:
        # Trích xuất feature cho 1 giao dịch
        features = await feature_extractor.extract_features_for_transaction(
            tx,
            mlflow_run_id,
        )

        # Lưu transaction_id để trace ngược khi cần audit
        features["transaction_id"] = str(tx.id)

        # Khởi tạo nhãn gian lận mặc định = 0 (hợp lệ)
        is_fraud = 0

        # Trường hợp 1: giao dịch đã được review thủ công trong metadata
        if tx.transaction_metadata and "fraud_review" in tx.transaction_metadata:
            if tx.transaction_metadata["fraud_review"].get("is_fraud", False):
                is_fraud = 1

        # Trường hợp 2: trạng thái AI review đã xác nhận gian lận
        if tx.ai_review_status and tx.ai_review_status == "CONFIRMED_FRAUD":
            is_fraud = 1

        # Trường hợp 3: kiểm tra bảng risk score đã confirm fraud
        # Dùng để tránh bỏ sót các giao dịch gian lận đã được đánh dấu trước đó
        if is_fraud == 0:
            risk_stmt = select(TransactionRiskScore).where(
                TransactionRiskScore.transaction_id == tx.id,
                TransactionRiskScore.is_confirmed_fraud == True,
            )
            risk_result = await session.exec(risk_stmt)
            risk_score = risk_result.first()

            if risk_score:
                is_fraud = 1

        # Gán nhãn cuối cùng cho giao dịch
        features["is_fraud"] = is_fraud

        # Thêm feature của giao dịch vào dataset tổng
        all_features.append(features)

    # Nếu không có feature nào được trích xuất → trả về DataFrame rỗng
    if not all_features:
        logger.warning("No features extracted, returning empty dataframe")
        return pd.DataFrame()

    # Chuyển danh sách feature dict thành DataFrame
    df = pd.DataFrame(all_features)

    # Log thông tin dataset lên MLflow (nếu có run_id)
    if mlflow_run_id:
        try:
            active_run = mlflow.active_run()
            in_correct_run = active_run and active_run.info.run_id == mlflow_run_id

            # Nếu đang ở đúng run → dùng nested run
            with mlflow.start_run(
                run_id=mlflow_run_id if not in_correct_run else None,
                nested=True if in_correct_run else False,
            ):
                # Log kích thước dataset
                mlflow.log_param("dataset_rows", len(df))
                mlflow.log_param("dataset_columns", len(df.columns))

                # Log tỷ lệ gian lận (rất quan trọng trong fraud detection)
                mlflow.log_param("fraud_ratio", df["is_fraud"].mean())

                # Log số lượng feature (trừ transaction_id và label)
                mlflow.log_param("feature_count", len(df.columns) - 2)

                # Log mẫu tên cột để debug
                columns_sample = df.columns.tolist()[:50]
                mlflow.log_param("columns_sample", columns_sample)

                # Log số lượng fraud và non-fraud
                mlflow.log_metric("fraud_count", int(df["is_fraud"].sum()))
                mlflow.log_metric(
                    "legitimate_count",
                    int(len(df) - df["is_fraud"].sum()),
                )

        except Exception as e:
            # Không để lỗi MLflow làm hỏng pipeline training
            logger.error(f"Error logging to MLflow: {e}")
            if mlflow.active_run():
                mlflow.end_run()

    # Xác định các cột cần one-hot encoding
    string_columns: list[str] = []

    for col in df.columns:
        if col not in ["transaction_id", "is_fraud"]:
            # Cột kiểu object nhưng không convert được sang số
            if df[col].dtype == object:
                try:
                    pd.to_numeric(df[col])
                except Exception:
                    string_columns.append(col)
            # Các cột mang tính phân loại theo tên
            elif any(
                keyword in col
                for keyword in ["status", "type", "category", "currency"]
            ):
                string_columns.append(col)

    # One-hot encoding các cột dạng categorical
    if string_columns:
        df = pd.get_dummies(
            df,
            columns=string_columns,
            drop_first=True,
        )

    # Xử lý các cột object còn sót lại
    for col in df.select_dtypes(include=["object"]).columns:
        if col != "transaction_id":
            try:
                df[col] = df[col].astype(str).astype("category")
            except Exception:
                # Nếu không encode được → loại bỏ cột
                logger.warning(
                    f"Dropping column {col} as it can't be properly encoded"
                )
                df = df.drop(columns=[col])

    # Điền giá trị thiếu bằng 0 để tránh lỗi khi train model
    df = df.fillna(0)

    # Log kích thước dataset cuối cùng
    logger.info(
        f"Prepared dataset with {df.shape[0]} rows, {df.shape[1]} columns"
    )

    return df



