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

class TransferRequestSchema(SQLModel):
    """Schema yêu cầu chuyển tiền."""
    sender_account_id: uuid.UUID                     # Tài khoản gửi
    receiver_account_number: str = Field(
        min_length=16, max_length=16
    )                                                 # Số tài khoản nhận
    amount: Decimal = Field(ge=0, decimal_places=2)   # Số tiền chuyển
    security_answer: str = Field(max_length=30)       # Câu trả lời bảo mật
    description: str = Field(max_length=250)          # Nội dung chuyển tiền


class TransferOTPVerificationSchema(SQLModel):
    """Schema xác thực OTP cho giao dịch chuyển tiền."""
    transfer_reference: str                           # Mã giao dịch
    otp: str = Field(min_length=6, max_length=6)      # Mã OTP


class TransferResponseSchema(SQLModel):
    """Schema phản hồi chuyển tiền."""
    status: str                                       # Trạng thái
    message: str                                      # Thông báo
    data: dict | None = None                          # Dữ liệu trả về

class CurrencyConversionSchema(SQLModel):
    """Schema kết quả chuyển đổi tiền tệ."""
    amount: Decimal                     # Số tiền sau chuyển đổi
    from_currency: str                  # Tiền tệ gốc
    to_currency: str                    # Tiền tệ đích
    exchange_rate: Decimal              # Tỷ giá áp dụng
    original_amount: Decimal            # Số tiền ban đầu
    converted_amount: Decimal           # Số tiền sau quy đổi
    conversion_fee: Decimal = Field(
        default=Decimal("0.00")
    )                                   # Phí chuyển đổi

class WithdrawalRequestSchema(SQLModel):
    account_number: str = Field(min_length=16, max_length=16) # Số tài khoản rút tiền
    amount: Decimal = Field(ge=0, decimal_places=2)          # Số tiền rút
    username: str = Field(min_length=1, max_length=12)        # Tên đăng nhập người rút
    description: str = Field(max_length=250)                    # Nội dung giao dịch

class TransactionHistoryResponseSchema(SQLModel):
    """Schema hiển thị lịch sử giao dịch."""

    id: uuid.UUID                     # ID giao dịch
    reference: str                    # Mã giao dịch
    amount: Decimal                   # Số tiền giao dịch
    description: str                  # Nội dung giao dịch
    transaction_type: TransactionTypeEnum      # Loại giao dịch
    transaction_category: TransactionCategoryEnum  # Credit / Debit
    transaction_status: TransactionStatusEnum  # Trạng thái giao dịch
    created_at: datetime              # Thời điểm tạo
    completed_at: datetime | None = None  # Thời điểm hoàn tất
    balance_after: Decimal            # Số dư sau giao dịch

    currency: str | None = None       # Tiền tệ giao dịch
    converted_amount: str | None = None  # Số tiền sau quy đổi (nếu có)
    from_currency: str | None = None  # Tiền tệ nguồn
    to_currency: str | None = None    # Tiền tệ đích
    counterparty_name: str | None = None     # Tên đối tác
    counterparty_account: str | None = None  # Tài khoản đối tác


class PaginatedTransactionResponseSchema(SQLModel):
    """Schema phân trang lịch sử giao dịch."""

    total: int                        # Tổng số giao dịch
    skip: int                         # Offset
    limit: int                        # Số bản ghi mỗi trang
    transactions: list[TransactionHistoryResponseSchema]  # Danh sách giao dịch


class TransactionFilterParamsSchema(SQLModel):
    """Schema filter lịch sử giao dịch."""

    start_date: datetime | None = Query(
        default=None,
        description="Lọc giao dịch từ ngày này (bao gồm)",
        example="2025-01-01T00:00:00Z",
    )
    end_date: datetime | None = Query(
        default=None,
        description="Lọc giao dịch đến ngày này (bao gồm)",
        example="2025-12-01T23:59:59Z",
    )
    transaction_type: TransactionTypeEnum | None = Query(
        default=None, description="Lọc theo loại giao dịch"
    )
    transaction_category: TransactionCategoryEnum | None = Query(
        default=None, description="Lọc theo Credit / Debit"
    )
    status: TransactionStatusEnum | None = Query(
        default=None, description="Lọc theo trạng thái giao dịch"
    )
    min_amount: Decimal | None = Query(
        default=None,
        ge=0,
        description="Lọc giao dịch có số tiền >= giá trị này",
    )
    max_amount: Decimal | None = Query(
        default=None,
        ge=0,
        description="Lọc giao dịch có số tiền <= giá trị này",
    )
class StatementRequestSchema(SQLModel):
    """Schema yêu cầu sao kê tài khoản."""

    start_date: datetime               # Ngày bắt đầu sao kê
    end_date: datetime                 # Ngày kết thúc sao kê
    account_number: str | None = Field(
        default=None,
        min_length=16,
        max_length=16,
        description="16-digit account number for specific account statements",
    )                                  # Số tài khoản (tùy chọn)


class StatementResponseSchema(SQLModel):
    """Schema phản hồi yêu cầu sao kê."""

    status: str                        # Trạng thái xử lý
    message: str                       # Thông báo
    task_id: str | None = None         # ID task xử lý nền (nếu có)
    statement_id: str | None = None    # ID sao kê
    generated_at: datetime | None = None  # Thời điểm tạo sao kê
    expires_at: datetime | None = None    # Thời điểm hết hạn sao kê
