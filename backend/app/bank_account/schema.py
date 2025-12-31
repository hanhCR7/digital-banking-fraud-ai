from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from backend.app.bank_account.enums import (
    AccountCurrencyEnum,
    AccountStatusEnum,
    AccountTypeEnum,
)

class BankAccountBaseSchema(SQLModel):
    """
    Schema nền tảng cho tài khoản ngân hàng.
    Chứa các thuộc tính dùng chung cho create, read và update.
    """

    account_type: AccountTypeEnum          # Loại tài khoản (thanh toán, tiết kiệm, doanh nghiệp...)
    currency: AccountCurrencyEnum           # Loại tiền tệ của tài khoản
    account_status: AccountStatusEnum = Field(
        default=AccountStatusEnum.Pending
    )                                       # Trạng thái tài khoản

    account_number: str | None = Field(
        default=None, unique=True, index=True
    )                                       # Số tài khoản (duy nhất)

    account_name: str                       # Tên hiển thị của tài khoản
    balance: float = Field(default=0.0)     # Số dư hiện tại

    is_primary: bool = Field(default=False) # Tài khoản chính của người dùng

    kyc_submitted: bool = Field(default=False)  # Đã gửi hồ sơ KYC hay chưa
    kyc_verified: bool = Field(default=False)   # KYC đã được xác minh hay chưa
    kyc_verified_by: UUID | None = Field(
        default=None
    )                                           # ID admin xác minh KYC

    interest_rate: float = Field(default=0.0)   # Lãi suất (áp dụng cho tài khoản tiết kiệm)


class BankAccountCreateSchema(BankAccountBaseSchema):
    """
    Schema dùng khi tạo mới tài khoản ngân hàng.
    Một số field có thể được hệ thống tự sinh (ví dụ account_number).
    """
    account_number: str | None = None


class BankAccountReadSchema(BankAccountBaseSchema):
    """
    Schema dùng để trả dữ liệu tài khoản ngân hàng cho client.
    Bao gồm các trường chỉ đọc như id, user_id, thời gian tạo/cập nhật.
    """
    id: UUID
    user_id: UUID
    account_number: str | None = None
    created_at: datetime
    updated_at: datetime


class BankAccountUpdateSchema(BankAccountBaseSchema):
    """
    Schema dùng để cập nhật thông tin tài khoản ngân hàng.
    Chỉ các field được truyền mới được cập nhật.
    """
    account_name: str | None = None
    is_primary: bool | None = None
    account_status: AccountStatusEnum | None = None
