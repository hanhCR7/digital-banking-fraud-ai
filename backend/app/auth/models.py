import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar
from pydantic import computed_field
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql as pg
from sqlmodel import Column, Field, Relationship, Boolean
from backend.app.auth.schema import BaseUserSchema
if TYPE_CHECKING:
    from backend.app.user_profile.models import Profile
    from backend.app.next_of_kin.models import NextOfKin
    from backend.app.bank_account.models import BankAccount
    from backend.app.transaction.models import Transaction
    from backend.app.user_role.models import UserRole

class User(BaseUserSchema, table=True):
    __tablename__: ClassVar[str] = "users"

    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )
    hashed_password: str
    failed_login_attempts: int = Field(default=0, sa_type=pg.SMALLINT)
    must_change_password: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    last_failed_login: datetime | None = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True))
    )
    otp: str = Field(max_length=6, default="")
    otp_expiry_time: datetime | None = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            onupdate=func.current_timestamp(),
        ),
    )
    deleted_at: datetime | None = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True))
    )
    # Mối quan hệ một-một với Profile
    profile: "Profile" = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "uselist": False,
            "lazy": "selectin",
        },
    )
    # Mối quan hệ N - 1 với Role
    user_roles: list["UserRole"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    # Mối quan hệ một-nhiều với NextOfKin
    next_of_kins: list["NextOfKin"] = Relationship(back_populates="user")
    # Mối quan hệ một-nhiều với BankAccount
    bank_accounts: list["BankAccount"] = Relationship(back_populates="user")
    # Các quan hệ 1-n với Transaction
    sent_transactions: list["Transaction"] = Relationship(
        back_populates="sender",
        sa_relationship_kwargs={"foreign_keys": "Transaction.sender_id"},
    )  # Giao dịch user gửi

    received_transactions: list["Transaction"] = Relationship(
        back_populates="receiver",
        sa_relationship_kwargs={"foreign_keys": "Transaction.receiver_id"},
    )  # Giao dịch user nhận

    processed_transactions: list["Transaction"] = Relationship(
        back_populates="processor",
        sa_relationship_kwargs={"foreign_keys": "Transaction.processed_by"},
    )  # Giao dịch user xử lý



    
    @computed_field
    @property
    def full_name(self) -> str:
        full_name = f"{self.last_name} {self.middle_name + ' ' if self.middle_name else ''}{self.first_name}"
        return full_name.title().strip()
