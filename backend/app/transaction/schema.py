import uuid
from datetime import datetime
from decimal import Decimal
from fastapi import Query
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel
from typing_extensions import Annotated
from backend.app.transaction.enums import (
    TransactionStatusEnum,
    TransactionTypeEnum,
    TransactionCategoryEnum
)
class TransactionBaseSchema(SQLModel):
    """Schema nền tảng cho giao dịch tài chính."""
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]  # Số tiền giao dịch
    description: str = Field(max_length=250)                   # Nội dung giao dịch
    reference: str = Field(unique=True, index=True)            # Mã giao dịch duy nhất
    transaction_type: TransactionTypeEnum                      # Loại giao dịch
    transaction_category: TransactionCategoryEnum              # Credit / Debit
    status: TransactionStatusEnum = Field(default=TransactionStatusEnum.Pending)  # Trạng thái
    balance_before: Annotated[Decimal, Field(decimal_places=2)]  # Số dư trước giao dịch
    balance_after: Annotated[Decimal, Field(decimal_places=2)]   # Số dư sau giao dịch
    transaction_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))  # Dữ liệu bổ sung (JSON)
    failed_reason: str | None = Field(default=None)  # Lý do thất bại (nếu có)

class TransactionCreateSchema(TransactionBaseSchema):
    pass


class TransactionReadSchema(TransactionBaseSchema):
    id: uuid.UUID

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False)
    )

    completed_at: datetime | None = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True)
    ) # Thời gian hoàn tất giao dịch

class TransactionUpdateSchema(TransactionBaseSchema):
    pass

class DepositRequestSchema(SQLModel):
    account_id: uuid.UUID# ID tài khoản nhận tiền
    amount: Decimal = Field(ge=0, decimal_places=2)# Số tiền nạp vào tài khoản
    description: str = Field(max_length=250)# Nội dung giao dịch

