import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, text
from sqlalchemy.dialects import postgresql as pg
from sqlmodel import Field, SQLModel


class RateLimitLog(SQLModel, table=True):
    """
    Bảng lưu log kiểm soát rate limiting cho các request vào hệ thống.

    Dùng để:
    - Theo dõi số lượng request theo IP / User / Endpoint
    - Phát hiện và xử lý hành vi spam / brute-force
    - Phục vụ audit và debug hệ thống
    """

    # Khóa chính UUID, sinh tự động cho mỗi bản ghi
    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )

    # Địa chỉ IP của client gửi request (được index để truy vấn nhanh)
    ip_address: str = Field(index=True)

    # ID người dùng (null nếu request chưa xác thực / ẩn danh)
    user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="users.id",
    )

    # Tên endpoint logic (vd: /auth/login, /users/me)
    endpoint: str

    # Tổng số request trong cửa sổ rate limit hiện tại
    request_count: int

    # HTTP method của request (GET, POST, PUT, DELETE, ...)
    request_method: str

    # Đường dẫn request thực tế được gọi
    request_path: str

    # Thời điểm bắt đầu cửa sổ rate limiting
    window_start: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=True,
        )
    )

    # Thời điểm kết thúc cửa sổ rate limiting
    window_end: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=True,
        )
    )

    # Thời điểm bị chặn request đến (null nếu chưa bị block)
    blocked_until: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # Thời điểm tạo bản ghi log (UTC, do server tự sinh)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
