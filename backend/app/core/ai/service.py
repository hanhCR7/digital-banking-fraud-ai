from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.ai.config import ai_settings
from backend.app.core.ai.enums import AIReviewStatusEnum
from backend.app.core.ai.models import TransactionRiskScore
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.ml.deployment import ModelInference, update_transaction_risk
from backend.app.transaction.enums import TransactionFailureReason
from backend.app.transaction.models import Transaction
from backend.app.transaction.utils import mark_transaction_failed

logger = get_logger()

class TransactionAIService:
    """
    Service chịu trách nhiệm phân tích giao dịch bằng AI
    - Gọi model inference để dự đoán gian lận
    - Lưu risk score vào DB
    - Cập nhật trạng thái giao dịch
    - Trả về kết quả cho API
    """
    def __init__(self, session: AsyncSession):
        # Async DB session để thao tác với database
        self.session = session
        # Service inference model AI
        self.model_inference = ModelInference(session)

    async def analyze_transaction(
        self, transaction: Transaction, user_id: UUID
    ) -> dict:
        """
        Phân tích một giao dịch để xác định mức độ rủi ro gian lận
        :param transaction: Giao dịch cần phân tích
        :param user_id: ID người dùng thực hiện giao dịch
        :return: Kết quả phân tích rủi ro
        """
        try:
            # Gọi model AI để dự đoán xác suất gian lận
            fraud_probability, prediction_details = (
                await self.model_inference.predict_fraud(transaction)
            )

            # Tạo bản ghi risk score cho giao dịch
            risk_score = TransactionRiskScore(
                transaction_id=transaction.id,
                risk_score=fraud_probability,
                # Các yếu tố rủi ro do model trả về
                risk_factors=prediction_details.get("risk_factors", {}),
                # Version model dùng để dự đoán
                ai_model_version=prediction_details.get("model_version", "unknown"),
            )

            # Lưu risk score vào database
            self.session.add(risk_score)

            # Cập nhật trạng thái và mức độ rủi ro của giao dịch
            await update_transaction_risk(
                transaction=transaction,
                fraud_probability=fraud_probability,
                risk_threshold=ai_settings.RISK_SCORE_THRESHOLD,
                prediction_details=prediction_details,
                session=self.session,
            )

            # Kiểm tra giao dịch có vượt ngưỡng rủi ro hay không
            needs_review = fraud_probability >= ai_settings.RISK_SCORE_THRESHOLD

            # Kết quả trả về cho client/API
            response = {
                "risk_score": fraud_probability,
                "risk_factors": prediction_details.get("risk_factors", {}),
                "needs_review": needs_review,
                # Đề xuất hành động dựa trên rủi ro
                "recommendation": "block" if needs_review else "allow",
                "model_version": prediction_details.get("model_version", "unknown"),
                "score_id": risk_score.id,
                "model_details": {
                    "model_name": prediction_details.get("model_name", "unknown"),
                    "prediction_time": prediction_details.get("prediction_time", None),
                    # Đánh dấu nếu dùng fallback model
                    "is_fallback": prediction_details.get("is_fallback", False),
                },
            }

            # Log cảnh báo nếu phát hiện giao dịch rủi ro cao
            if needs_review:
                logger.warning(
                    f"Phát hiện giao dịch rủi ro cao: {transaction.id}, "
                    f"Score: {fraud_probability}, "
                    f"Factors: {prediction_details.get('risk_factors', {})}"
                )

            return response

        except Exception as e:
            # Log lỗi khi phân tích giao dịch thất bại
            logger.error(f"Lỗi khi phân tích giao dịch: {e}")

            # Fallback response để đảm bảo hệ thống an toàn
            return {
                "risk_score": 0.8,                 # Điểm rủi ro mặc định cao
                "risk_factors": {"error": str(e)},
                "needs_review": True,
                "recommendation": "block",         # Chặn giao dịch để an toàn
                "model_version": "fallback",
                "error": str(e),
            }

    async def handle_flagged_transaction(
        self,
        transaction: Transaction,
        risk_analysis: dict[str, Any],
    ) -> None:
        """Xử lý giao dịch đã bị AI đánh dấu là đáng ngờ (FLAGGED). """
        try:
            # Đánh dấu giao dịch thất bại do hoạt động đáng ngờ
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SUSPICIOUS_ACTIVITY,
                details={
                    # Điểm rủi ro tổng
                    "risk_score": risk_analysis["risk_score"],
                    # Các yếu tố đóng góp vào điểm rủi ro
                    "risk_factors": risk_analysis["risk_factors"],
                    # Phiên bản mô hình AI sử dụng
                    "model_version": risk_analysis.get("model_version", "unknown"),
                    # Thông tin bổ sung về mô hình (nếu có)
                    "model_details": risk_analysis.get("model_details", {}),
                },
                session=self.session,
                # Thông báo chuẩn trả về cho người dùng
                error_message=(
                    "Giao dịch này đã bị đánh dấu là có khả năng gian lận."
                    "Một nhân viên phụ trách tài khoản sẽ xem xét giao dịch "
                    "trước khi nó được phê duyệt hoặc bị từ chối."
                ),
            )

            # Cập nhật trạng thái AI review của giao dịch
            transaction.ai_review_status = AIReviewStatusEnum.FLAGGED

            # Commit thay đổi vào database
            await self.session.commit()

        except Exception as e:
            # Ghi log lỗi để theo dõi và audit
            logger.error(f"Lỗi khi xử lý giao dịch đã bị đánh dấu: {str(e)}")
            raise
    async def get_transaction_risk_history(
        self, 
        user_id: UUID, 
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_risk_score: float | None = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Lấy lịch sử đánh giá rủi ro giao dịch của một người dùng
        Hỗ trợ:
        - Lọc theo khoản thời gian
        - lọc theo ngưỡng risk score tối thiểu
        - Giới hạn sô lượng bản ghi trả về
        """
        try:
            stmt = (
                select(Transaction, TransactionRiskScore)
                .join(TransactionRiskScore)
                .where(
                    Transaction.id == TransactionRiskScore.transaction_id,# join theo transaction_id
                    Transaction.sender_id == user_id # CHỉ lấy transaction user gửi
                )
            )
            if start_date:
                stmt = stmt.where(TransactionRiskScore.created_at >= start_date)

            if end_date:
                stmt = stmt.where(TransactionRiskScore.created_at <= end_date)

            if min_risk_score:
                stmt = stmt.where(TransactionRiskScore.risk_score >= min_risk_score)

            # Sắp xếp theo thời gian mới nhất và giới hạn số bản ghi
            stmt = stmt.order_by(desc(TransactionRiskScore.created_at)).limit(limit)

            result = await self.session.exec(stmt)
            # Lấy list (Transaction, TransactionRiskScore)
            tx_risk_pairs = result.all()
            response = []
            # Chuẩn hóa dữ liệu trả về cho API
            for tx, risk in tx_risk_pairs:
                response.append(
                    {
                        "transaction_id": str(tx.id),
                        "reference": tx.reference,
                        "amount": str(tx.amount),
                        "date": tx.created_at.isoformat(),
                        "risk_score": risk.risk_score,
                        "risk_factors": risk.risk_factors,
                        "ai_review_status": tx.ai_review_status,
                        "model_version": risk.ai_model_version
                    }
                )
            return response

        except Exception as e:
            logger.error(f"Lỗi khi lấy lịch sử rủi ro: {str(e)}")
            raise
async def review_flagged_transaction(
    self,
    transaction_id: UUID,
    reviewer_id: UUID,
    is_fraud: bool,
    notes: str | None = None,
    session: AsyncSession = Depends(get_session),
    approve_transaction: bool = False
) -> dict[str, Any]:
    """
    Review thủ công một giaO dịch đã bị AI gắn cờ rủi ro
    Chức năng;
    - Xác nhận giao dịch là gian lận hoặc hợp lệ
    - Cập nhật trạng thái AI review
    - Lưu thông tin reviewer & audit metadata
    - (Tùy chọn) hoàn tất giao dịch nếu được phê duyệt
    """
    try:
        # Truy vấn giao dịch kèm theo risk score
        tx_stmt = (
            select(Transaction, TransactionRiskScore)
            .join(TransactionRiskScore)
            .where(
                Transaction.id == TransactionRiskScore.transaction_id,
                Transaction.id == transaction_id
            )
        )
        result = await session.exec(tx_stmt)
        tx_risk = result.first()
        # Không tìm thấy giao dịch hoặc chưa có risk score
        if not tx_risk:
            raise ValueError(f"Không tìm thấy giao dịch {transaction_id} hoặc chưa có điểm rủi ro.")
        transaction, risk_score = tx_risk
        # Cập nhật kết quả review vào bảng risk score
        risk_score.is_confirmed_fraud = is_fraud
        risk_score.reviewed_by = reviewer_id
        # Cập nhật trạng thái review AI của giao dịch
        transaction.ai_review_status = (
            AIReviewStatusEnum.CONFIRMED_FRAUD
            if is_fraud
            else AIReviewStatusEnum.CLEARED
        )
        # Đảm bảo metadata tồn tại
        if not transaction.transaction_metadata:
            transaction.transaction_metadata = {}
        # Lưu audit trail cho quá trình review
        transaction.transaction_metadata["fraud_review"] = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": str(reviewer_id),
            "is_fraud": is_fraud,
            "notes": notes or ""
        }
        # Nếu được phê duyệt và không phải gian lận -> hoàn tất giao dịch
        if approve_transaction and not is_fraud:
            from backend.app.api.services.transaction import (
                _complete_approved_transfer,
                _complete_approved_withdrawal
            ) 
            # Xử lý theo loại giao dịch
            if transaction.transaction_type == "Transfer":
                await _complete_approved_transfer(transaction, session)
            elif transaction.transaction_type == "Withdrawal":
                await _complete_approved_withdrawal(transaction, session)
        # Đưa entity vào session để lưu thay đổi
        session.add(transaction)
        session.add(risk_score)
        # Commit toàn bộ thay đổi
        await session.commit()
        # Trả về kết quả cho API
        return {
            "status": "success",
            "transaction_id": str(transaction.id),
            "is_fraud": is_fraud,
            "approved": approve_transaction and not is_fraud,
            "new_status": transaction.ai_review_status
        }
    except Exception as e:
        logger.error(f"Lỗi khi duyệt giao dịch bị đánh dấu: {str(e)}")
        # Rollback để đảm bảo tính toàn vẹn dữ liệu
        await session.rollback()
        raise

