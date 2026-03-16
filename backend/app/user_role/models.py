from datetime import datetime
import uuid
from typing import TYPE_CHECKING
from sqlmodel import SQLModel, Field, ForeignKey, Column, String, Relationship
from sqlalchemy.dialects.postgresql import UUID

if TYPE_CHECKING:
    from backend.app.auth.models import User
    from backend.app.role.models import Role

class UserRole(SQLModel, table=True):

    user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True
        )
    )
    role_code: str = Field(
        sa_column=Column(
            String,
            ForeignKey("role.code", ondelete="CASCADE"),
            primary_key=True
        )
    )
    assigned_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False
    )

    # Mối quan hệ ngược với User và Role
    user: "User" = Relationship(back_populates="user_roles")
    role: "Role" = Relationship(back_populates="user_roles")