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
from backend.app.transaction.enums import TransactionFailureReason
from backend.app.transaction.models import Transaction
from backend.app.transaction.utils import mark_transaction_failed
from .transaction_analyzer import TransactionAnalyzer

logger = get_logger()

class TransactionAiService:
    """Service xử lý phân tích rủi ro giao dịch bằng AI."""

    def __init__(self, session: AsyncSession):
        # Session DB dùng xuyên suốt vòng đời service
        self.session = session
        # Analyzer chịu trách nhiệm tính toán risk score
        self.analyzer = TransactionAnalyzer()

    async def analyze_transaction(
        self,
        transaction: Transaction,
        user_id: UUID,
    ) -> dict:
        """Phân tích giao dịch và đưa ra quyết định xử lý."""
        try:
            # Gọi analyzer để tính điểm rủi ro
            risk_score, risk_factors = await self.analyzer.analyze_transaction(
                transaction, user_id, self.session
            )

            # Lưu kết quả risk score vào database
            risk_score_record = TransactionRiskScore(
                transaction_id=transaction.id,
                risk_score=risk_score,
                risk_factors=risk_factors,
                ai_model_version=ai_settings.MODEL_VERSION,
            )

            self.session.add(risk_score_record)

            # Xác định giao dịch có cần review thủ công không
            needs_review = risk_score >= ai_settings.RISK_SCORE_THRESHOLD

            # Cập nhật trạng thái AI review cho giao dịch
            transaction.ai_review_status = (
                AIReviewStatusEnum.FLAGGED
                if needs_review
                else AIReviewStatusEnum.CLEARED
            )

            # Commit toàn bộ thay đổi (risk score + transaction status)
            await self.session.commit()

            # Refresh để lấy ID bản ghi risk score
            await self.session.refresh(risk_score_record)

            # Response trả về cho tầng API / workflow
            response = {
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "needs_review": needs_review,
                "recommendation": "block" if needs_review else "allow",
                "model_version": ai_settings.MODEL_VERSION,
                "score_id": risk_score_record.id,
            }

            # Ghi log cảnh báo nếu giao dịch rủi ro cao
            if needs_review:
                logger.warning(
                    f"High risk transaction detected | "
                    f"transaction_id={transaction.id} | "
                    f"risk_score={risk_score}"
                )

            return response

        except Exception as e:
            # Fail-safe: nếu AI lỗi → mặc định coi là rủi ro cao
            logger.error(f"Error analyzing transaction: {e}")

            return {
                "risk_score": 0.8,
                "risk_factors": {"error": str(e)},
                "needs_review": True,
                "recommendation": "block",
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
                    "This transaction has been flagged as potentially fraudulent. "
                    "An account executive will review the transaction before it is "
                    "either approved or rejected."
                ),
            )

            # Cập nhật trạng thái AI review của giao dịch
            transaction.ai_review_status = AIReviewStatusEnum.FLAGGED

            # Commit thay đổi vào database
            await self.session.commit()

        except Exception as e:
            # Ghi log lỗi để theo dõi và audit
            logger.error(f"Error handling flagged transaction: {str(e)}")
            raise
    async def get_transaction_risk_history(
        self, 
        user_id: UUID, 
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_risk_score: float | None = None
    ) -> list[TransactionRiskScore]:
        try:
            query = (
                select(TransactionRiskScore).join(Transaction)
                .where(Transaction.sender_id == user_id)
            )
            if start_date:
                query = query.where(TransactionRiskScore.created_at >= start_date)

            if end_date:
                query = query.where(TransactionRiskScore.created_at <= end_date)

            if min_risk_score:
                query = query.where(TransactionRiskScore.risk_score >= min_risk_score)

            result = await self.session.exec(query)
            return list(result)

        except Exception as e:
            logger.error(f"Error fetching risk history: {str(e)}")
            raise
    async def mark_confirmed_fraud(
        self,
        transaction_id: UUID,
        reviewer_id: UUID,
        notes: str | None
    ) -> TransactionRiskScore:
        try:
            query = (
                select(Transaction, TransactionRiskScore)
                .join(TransactionRiskScore)
                .where(Transaction.id == transaction_id)
            )

            result = await self.session.exec(query)
            transaction_data = result.first()

            if not transaction_data:
                raise ValueError(
                f"Transaction {transaction_id} not found or has no risk score"
            )
            transaction, risk_score = transaction_data

            risk_score.is_confirmed_fraud = True
            risk_score.reviewed_by = reviewer_id

            if transaction:
                transaction.ai_review_status=AIReviewStatusEnum.CONFIRMED_FRAUD
                if not transaction.transaction_metadata:
                    transaction.transaction_metadata = {}

                transaction.transaction_metadata["fraud_review"] = {
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "reviewed_by": str(reviewer_id),
                    "notes": notes,
                }
            await self.session.commit()
            await self.session.refresh(risk_score)

            return risk_score
        except Exception as e:
            logger.error(f"Error marking confirmed fraud: {str(e)}")
            raise
