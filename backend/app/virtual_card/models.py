import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship

from backend.app.virtual_card.schema import VirtualCardBaseSchema

if TYPE_CHECKING:
    # Import chỉ dùng cho type hint, tránh vòng lặp import khi runtime
    from backend.app.auth.models import User
    from backend.app.bank_account.models import BankAccount


# Model bảng VirtualCard lưu thông tin thẻ ảo
class VirtualCard(VirtualCardBaseSchema, table=True):
    # Khóa chính của thẻ ảo
    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )

    # Thời điểm tạo thẻ
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # Thời điểm cập nhật gần nhất
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            onupdate=func.current_timestamp(),
        ),
    )

    # Giá trị CVV đã được hash để đảm bảo bảo mật
    cvv_hash: str | None = Field(default=None)

    # Số dư khả dụng trên thẻ
    available_balance: float = Field(default=0.0)

    # Tổng số tiền đã nạp vào thẻ
    total_topped_up: float = Field(default=0.0)

    # Thời điểm nạp tiền gần nhất
    last_top_up_date: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # Thời điểm thẻ bị khóa
    blocked_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    # Tổng số tiền đã chi tiêu trong ngày
    total_spend_today: float = Field(default=0.0)

    # Tổng số tiền đã chi tiêu trong tháng hiện tại
    total_spent_this_month: float = Field(default=0.0)

    # Thời điểm giao dịch gần nhất
    last_transaction_date: datetime | None = Field(default=None)

    # Số tiền của giao dịch gần nhất
    last_transaction_amount: float | None = Field(default=None)

    # Thời điểm yêu cầu phát hành thẻ vật lý
    physical_card_requested_at: datetime | None = Field(default=None)

    # Thông tin địa chỉ giao thẻ vật lý
    delivery_address: str | None = Field(default=None)
    delivery_city: str | None = Field(default=None)
    delivery_country: str | None = Field(default=None)
    delivery_postal_code: str | None = Field(default=None)

    # Trạng thái phát hành thẻ vật lý
    physical_card_status: str | None = Field(default=None)

    # Người thực hiện khóa thẻ (admin hoặc chủ thẻ)
    blocked_by: uuid.UUID | None = Field(foreign_key="users.id", nullable=True)

    # Metadata mở rộng của thẻ (lưu dạng JSON)
    card_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))

    # Liên kết thẻ với tài khoản ngân hàng
    bank_account_id: uuid.UUID = Field(
        foreign_key="bankaccount.id",
        ondelete="CASCADE",
    )

    # Quan hệ tới bảng BankAccount
    bank_account: "BankAccount" = Relationship(back_populates="virtual_cards")

    # Quan hệ tới người đã khóa thẻ
    blocked_by_user: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "VirtualCard.blocked_by",
        }
    )

    @property
    def masked_card_number(self) -> str:
        # Trả về số thẻ đã được che để hiển thị an toàn
        if not self.card_number:
            return ""
        return f"**** **** **** {self.card_number[-4:]}"

    @property
    def last_four_digits(self) -> str:
        # Lấy 4 số cuối của số thẻ
        if not self.card_number:
            return ""
        return self.card_number[-4:]
