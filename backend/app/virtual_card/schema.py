from datetime import date, datetime
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

from backend.app.virtual_card.enums import (
    CardBlockReasonEnum,
    VirtualCardBrandEnum,
    VirtualCardCurrencyEnum,
    VirtualCardStatusEnum,
    VirtualCardTypeEnum,
)


# Schema cơ sở cho thẻ ảo (dùng chung cho create / read / update)
class VirtualCardBaseSchema(SQLModel):
    card_type: VirtualCardTypeEnum                 # Loại thẻ (debit / credit)
    card_brand: VirtualCardBrandEnum = Field(      # Thương hiệu thẻ
        default=VirtualCardBrandEnum.Visa
    )
    currency: VirtualCardCurrencyEnum              # Loại tiền tệ sử dụng
    card_status: VirtualCardStatusEnum = Field(    # Trạng thái thẻ
        default=VirtualCardStatusEnum.Pending
    )
    daily_limit: float = Field(gt=0)                # Hạn mức chi tiêu mỗi ngày
    monthly_limit: float = Field(gt=0)              # Hạn mức chi tiêu mỗi tháng
    name_on_card: str = Field(max_length=50)        # Tên in trên thẻ
    expiry_date: date                               # Ngày hết hạn thẻ
    is_active: bool = Field(default=True)           # Trạng thái kích hoạt thẻ
    is_physical_card_requested: bool = Field(       # Đã yêu cầu thẻ vật lý hay chưa
        default=False
    )
    block_reason: CardBlockReasonEnum | None = None # Lý do khóa thẻ
    block_reason_description: str | None = Field(   # Mô tả chi tiết lý do khóa
        default=None
    )
    card_number: str | None = Field(default=None)   # Số thẻ (chỉ dùng nội bộ)
    card_metadata: dict | None = Field(default=None)# Metadata mở rộng của thẻ


# Schema dùng khi tạo thẻ ảo mới
class VirtualCardCreateSchema(VirtualCardBaseSchema):
    bank_account_id: UUID                           # Tài khoản ngân hàng liên kết
    expiry_date: date | None = None                 # Ngày hết hạn (có thể auto-generate)


# Schema trả về thông tin thẻ ảo
class VirtualCardReadSchema(VirtualCardBaseSchema):
    id: UUID                                        # ID thẻ
    bank_account_id: UUID                           # ID tài khoản ngân hàng
    last_four_digits: str | None = None             # 4 số cuối của số thẻ
    created_at: datetime                            # Thời điểm tạo thẻ
    updated_at: datetime | None = None              # Thời điểm cập nhật gần nhất


# Schema dùng để cập nhật thông tin thẻ
class VirtualCardUpdateSchema(VirtualCardBaseSchema):
    daily_limit: float | None = Field(default=None, gt=0)    # Cập nhật hạn mức ngày
    monthly_limit: float | None = Field(default=None, gt=0)  # Cập nhật hạn mức tháng
    is_active: bool | None = Field(default=None)              # Bật / tắt thẻ


# Schema dùng khi khóa thẻ
class VirtualCardBlockSchema(VirtualCardBaseSchema):
    block_reason: CardBlockReasonEnum = Field()     # Lý do khóa thẻ
    block_reason_description: str = Field()         # Mô tả lý do khóa
    blocked_at: datetime = Field()                  # Thời điểm khóa thẻ
    blocked_by: UUID = Field()                      # Người thực hiện khóa thẻ


# Schema trạng thái thẻ (dùng cho màn hình tổng quan)
class VirtualCardStatusSchema(VirtualCardBaseSchema):
    card_status: VirtualCardStatusEnum = Field()    # Trạng thái hiện tại của thẻ
    available_balance: float                        # Số dư khả dụng
    daily_limit: float = Field()                    # Hạn mức ngày
    monthly_limit: float = Field()                  # Hạn mức tháng
    total_spend_today: float                        # Tổng chi tiêu hôm nay
    total_spend_this_month: float                   # Tổng chi tiêu trong tháng
    last_transaction_date: datetime | None = None   # Giao dịch gần nhất
    last_transaction_amount: float | None = None    # Số tiền giao dịch gần nhất


# Schema yêu cầu phát hành thẻ vật lý
class PhysicalCardRequestSchema(SQLModel):
    delivery_address: str = Field(max_length=200)   # Địa chỉ nhận thẻ
    city: str = Field(max_length=100)               # Thành phố
    country: str = Field(max_length=100)            # Quốc gia
    postal_code: str = Field(max_length=20)         # Mã bưu chính


# Schema nạp tiền vào thẻ
class CardTopUpSchema(SQLModel):
    account_number: str = Field(                    # Số tài khoản nguồn
        min_length=16, max_length=16
    )
    amount: float = Field(gt=0)                     # Số tiền nạp
    description: str = Field(max_length=250)        # Nội dung nạp tiền


# Schema phản hồi khi nạp tiền
class CardTopUpResponseSchema(SQLModel):
    status: str                                     # Trạng thái xử lý
    message: str                                    # Thông báo kết quả
    data: dict | None = None                        # Dữ liệu bổ sung (nếu có)


# Schema phản hồi khi xóa thẻ
class CardDeleteResponseSchema(SQLModel):
    status: str                                     # Trạng thái xóa
    message: str                                    # Thông báo kết quả
    deleted_at: datetime                            # Thời điểm xóa thẻ


# Schema đơn giản dùng cho API khóa thẻ
class CardBlockSchema(SQLModel):
    block_reason: CardBlockReasonEnum               # Lý do khóa
    block_reason_description: str = Field(          # Mô tả lý do
        max_length=250
    )
