from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import get_all_user_profiles
from backend.app.api.services.user_role import user_role_service
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.schema import (
    PaginatedProfileResponseSchema,
    ProfileResponseSchema,
)
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema

logger = get_logger()

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get(
    "/all",
    response_model=PaginatedProfileResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def list_user_profiles(
    current_user = Depends(require_permission(PermissionChoicesSchema.VIEW_ALL_PROFILES)),
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1),
) -> PaginatedProfileResponseSchema:
    """Lấy tất cả hồ sơ người dùng với phân trang (chỉ dành cho quản lý chi nhánh)"""
    try:
        # Gọi service layer để lấy danh sách user và tổng số bản ghi
        users, total_count = await get_all_user_profiles(
            session=session, current_user=current_user, skip=skip, limit=limit
        )
        role = await user_role_service.get_user_role(session, current_user.id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nguời dùng không có vai trò"
            )
        # Chuẩn hoá danh sách user sang schema response cho client
        profile_responses = [
            ProfileResponseSchema(
                username=user.username or "",
                first_name=user.first_name or "",
                middle_name=user.middle_name or "",
                last_name=user.last_name or "",
                email=user.email or "",
                id_no=str(user.id_no) if user.id_no else "",
                role=role,
                profile=user.profile,
            )
            for user in users
        ]
        # Trả về dữ liệu theo dạng phân trang (profiles + total + skip + limit)
        return PaginatedProfileResponseSchema(
            profiles=profile_responses, total=total_count, skip=skip, limit=limit
        )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi hệ thống: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi hệ thống.",
                "action": "Vui lòng thử lại sau.",
            },
        )