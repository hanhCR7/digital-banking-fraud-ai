import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.db import get_session
from backend.app.api.services.user_role import user_role_service
from backend.app.api.services.security import require_role
from backend.app.role.schema import RoleChoicesSchema
from backend.app.user_role.schema import AssignRoleRequest
from backend.app.core.logging import get_logger

logger = get_logger()

router = APIRouter(
    prefix="/admin",
    tags=["User Roles"],
)


@router.get("/roles", status_code=status.HTTP_200_OK, dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))])
async def get_roles(
    session: AsyncSession = Depends(get_session),
):
    """Lấy danh sách vai trò"""
    try:
        roles = await user_role_service.get_roles(session)
        return {
            "data": [
                {
                    "code": role.code,
                    "description": role.description,
                }
                for role in roles
            ]
        }
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách vai trò: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể lấy danh sách vai trò",
                "action": "Vui lòng thử lại sau",
            },
        )


@router.get(
    "/users/{user_id}/roles",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def get_user_roles(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Lấy danh sách vai trò của người dùng"""
    try:
        role = await user_role_service.get_user_role(session, user_id)
        if role is None:
            return{
                "message": "Người dùng không có vai trò!",
                "user_id": user_id,
                "role": None
            }
        return {
            "user_id": user_id,
            "roles": role.value
        }
    except Exception as e:
        logger.error(f"Lỗi khi lấy vai trò của user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể lấy vai trò của người dùng",
                "action": "Vui lòng thử lại sau",
            },
        )


@router.post(
    "/users/{user_id}/roles",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def assign_role_to_user(
    user_id: uuid.UUID,
    payload: AssignRoleRequest,
    session: AsyncSession = Depends(get_session),
):
    """Gán vai trò cho người dùng"""

    try:
        await user_role_service.assign_role_to_user(
            session=session,
            user_id=user_id,
            role=payload.role,
        )

        return {
            "status": "success",
            "message": "Gán vai trò cho người dùng thành công",
            "user_id": user_id,
            "role": payload.role.value,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "message": str(e),
            },
        )

    except Exception as e:
        logger.error(
            f"Lỗi khi gán role {payload.role} cho user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể gán vai trò cho người dùng",
            },
        )


