from typing import TYPE_CHECKING
from sqlmodel import SQLModel, Field, Column, String, Relationship

if TYPE_CHECKING:
    from backend.app.user_role.models import UserRole
    from backend.app.role_permission.models import RolePermission


class Role(SQLModel, table=True):
    code: str = Field(
        sa_column=Column(
            String(50),
            primary_key=True
        )
    )
    description: str | None = Field(
        sa_column=Column(
            String(255),
            default=None
        )
    )

    user_roles: list["UserRole"] = Relationship(back_populates="role")
    role_permissions: list["RolePermission"] = Relationship(back_populates="role")
