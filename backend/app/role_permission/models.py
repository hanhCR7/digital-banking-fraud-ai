from typing import TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from backend.app.role.models import Role
    from backend.app.permission.models import Permission

class RolePermission(SQLModel, table=True):
    role_code: str = Field(foreign_key="role.code", primary_key=True)
    permission_code: str = Field(foreign_key="permission.code", primary_key=True)

    # Mối quan hệ ngược với User và Role
    role: "Role" = Relationship(back_populates="role_permissions")
    permission: "Permission" = Relationship(back_populates="role_permissions")
