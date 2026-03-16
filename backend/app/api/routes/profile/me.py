from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.profile import get_user_with_profile
from backend.app.api.services.user_role import user_role_service
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.schema import ProfileResponseSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema

logger = get_logger()

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get(
        "/me", 
        response_model=ProfileResponseSchema, 
        status_code=status.HTTP_200_OK,
)
async def get_my_profile(
    current_user = Depends(require_permission(
        PermissionChoicesSchema.VIEW_MY_PROFILE
    )),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponseSchema:
    """Lấy thông tin hồ sơ người dùng hiện tại"""
    try:
        # Lấy người dùng cùng với hồ sơ của họ qua id
        user_with_profile = await get_user_with_profile(current_user.id, session)
        role = await user_role_service.get_user_role(session, current_user.id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nguời dùng không có vai trò"
            )
        if not user_with_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Người dùng không tồn tại.",
                    "action": "Vui lòng thử lại sau hoặc liên hệ với bộ phận hỗ trợ.",
                },
            )
        # Chuẩn hoá dữ liệu trả về cho client theo schema response
        response = ProfileResponseSchema(
            username=user_with_profile.username or "",
            first_name=user_with_profile.first_name or "",
            middle_name=user_with_profile.middle_name or "",
            last_name=user_with_profile.last_name or "",
            email=user_with_profile.email or "",
            id_no=str(user_with_profile.id_no) if user_with_profile.id_no else "",
            role=role,
            profile=user_with_profile.profile,
        )
        logger.debug(f"Đã lấy thông tin hồ sơ thành công cho người dùng {user_with_profile.id}")
        return response
    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Lỗi không mong muốn khi lấy thông tin hồ sơ: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi hệ thống.",
                "action": "Vui lòng thử lại sau.",
            },
        )