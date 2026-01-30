from sqlmodel import SQLModel, Field, Column, String, Relationship
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.app.role_permission.models import RolePermission

class Permission(SQLModel, table=True):
    code: str = Field(
        sa_column=Column(
            String(50),
            primary_key=True,
            index=True,
        )
    )
    description: str | None = Field(
        sa_column=Column(
            String(255),
            nullable=True,
            default=None,
        )
    )
    role_permissions: list["RolePermission"] = Relationship(back_populates="permission")
