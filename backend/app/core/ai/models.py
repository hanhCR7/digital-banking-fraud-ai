import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


# Model lưu trữ kết quả đánh giá rủi ro giao dịch do hệ thống AI thực hiện
class TransactionRiskScore(SQLModel, table=True):
    """
    Bảng lưu trữ kết quả đánh giá rủi ro của giao dịch do AI phân tích.
    """

    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )
    transaction_id: UUID = Field(foreign_key="transaction.id", index=True)
    # Điểm rủi ro (0 = an toàn, 1 = rủi ro cao)
    risk_score: float = Field(ge=0, le=1, index=True)
    # Các yếu tố rủi ro do AI phát hiện (dạng JSON)
    risk_factors: dict = Field(sa_column=Column(JSONB))
    # Phiên bản mô hình AI sử dụng để đánh giá
    ai_model_version: str
    # Thời điểm tạo bản ghi đánh giá (UTC)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    # Người kiểm duyệt thủ công (nếu có)
    reviewed_by: UUID | None = Field(default=None, foreign_key="users.id", nullable=True)
    # Kết quả xác nhận gian lận cuối cùng
    is_confirmed_fraud: bool | None = Field(default=None)
    
