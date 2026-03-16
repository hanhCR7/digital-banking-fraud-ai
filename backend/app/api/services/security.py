from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.auth.models import User
from backend.app.core.db import get_session
from fastapi import Depends, HTTPException, status
from backend.app.api.routes.auth.deps import get_current_user
from backend.app.permission.schema import PermissionChoicesSchema
from backend.app.role.schema import RoleChoicesSchema
from backend.app.api.services.permissions import permission_service
from backend.app.api.services.user_role import user_role_service

def require_permission(permission: PermissionChoicesSchema):
    async def check_user(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
    ):
        permissions = await permission_service.get_user_permission(
            user_id=current_user.id,
            session=session
        )
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
    async def check_user(
            current_user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_session)
        ):
        user_role = await user_role_service.get_user_role(
            session=session,
            user_id=current_user.id
        )
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