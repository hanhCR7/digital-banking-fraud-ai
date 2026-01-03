import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from backend.app.transaction.schema import TransactionBaseSchema

if TYPE_CHECKING:
    from backend.app.auth.models import User
    from backend.app.bank_account.models import BankAccount

class Transaction(TransactionBaseSchema, table=True):
    """Model bảng giao dịch tài chính."""

    id: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True),
        default_factory=uuid.uuid4,
    )  # ID giao dịch

    sender_account_id: uuid.UUID | None = Field(
        default=None, foreign_key="bankaccount.id"
    )  # Tài khoản gửi

    receiver_account_id: uuid.UUID | None = Field(
        default=None, foreign_key="bankaccount.id"
    )  # Tài khoản nhận

    sender_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")      # User gửi
    receiver_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")    # User nhận
    processed_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")   # Người xử lý

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
    )  # Thời điểm tạo

    completed_at: datetime | None = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True))
    )  # Thời điểm hoàn tất

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), onupdate=func.current_timestamp()),
    )  # Cập nhật cuối

    transaction_metadata: dict | None = Field(
        default=None, sa_column=Column(JSONB)
    )  # Dữ liệu bổ sung

    sender_account: "BankAccount" = Relationship(
        back_populates="sent_transactions",
        sa_relationship_kwargs={"foreign_keys": "Transaction.sender_account_id"},
    )  # Quan hệ tài khoản gửi

    receiver_account: "BankAccount" = Relationship(
        back_populates="received_transactions",
        sa_relationship_kwargs={"foreign_keys": "Transaction.receiver_account_id"},
    )  # Quan hệ tài khoản nhận

    sender: "User" = Relationship(
        back_populates="sent_transactions",
        sa_relationship_kwargs={"foreign_keys": "Transaction.sender_id"},
    )  # User gửi

    receiver: "User" = Relationship(
        back_populates="received_transactions",
        sa_relationship_kwargs={"foreign_keys": "Transaction.receiver_id"},
    )  # User nhận

    processor: "User" = Relationship(
        back_populates="processed_transactions",
        sa_relationship_kwargs={"foreign_keys": "Transaction.processed_by"},
    )  # User xử lý
class IdempotencyKey(SQLModel, table=True):
    """Model lưu idempotency key cho các request quan trọng."""
    id: uuid.UUID = Field(
        sa_column=Column(pg.UUID(as_uuid=True), primary_key=True),
        default_factory=uuid.uuid4,
    )  # ID bản ghi
    key: str = Field(index=True, unique=True)  # Idempotency key (duy nhất)
    user_id: uuid.UUID = Field(foreign_key="users.id")  # Người gửi request
    endpoint: str  # Endpoint áp dụng key
    response_code: int  # HTTP status đã trả
    response_body: dict = Field(sa_column=Column(JSONB))  # Response cache
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
    )  # Thời điểm tạo
    expires_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
    )  # Thời điểm hết hạn
