from fastapi import Depends, HTTPException, status
from backend.app.api.routes.auth.deps import get_current_user
from backend.app.permission.schema import PermissionChoicesSchema
from backend.app.role.schema import RoleChoicesSchema

def require_permission(permission: PermissionChoicesSchema):
    async def check_user(current_user: dict = Depends(get_current_user)):
        permissions: list[str] = current_user.get("permissions", [])
        if permission.value not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Bạn không có quyền thực hiện hành động này.",
                    "required_permission": permission.value
                }
            )
        return current_user
    return check_user
def require_role(*role: RoleChoicesSchema):
    async def check_user(current_user: dict = Depends(get_current_user)):
        user_role: str | None = current_user.get("role")
        if user_role is None or user_role not in [r.value for r in role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Bạn không có vai trò phù hợp.",
                    "required_roles": [r.value for r in role]
                }
            )
        return current_user
    return check_user