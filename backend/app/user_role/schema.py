from sqlmodel import SQLModel
from backend.app.role.schema import RoleChoicesSchema
class AssignRoleRequest(SQLModel):
    role: RoleChoicesSchema
