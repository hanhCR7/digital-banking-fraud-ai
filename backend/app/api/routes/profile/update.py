from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import update_user_profile
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.models import Profile
from backend.app.user_profile.schema import ProfileUpdateSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema

logger = get_logger()

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.patch(
    "/update", 
    response_model=Profile, 
    status_code=status.HTTP_200_OK,
)
async def update_profile(
    profile_data: ProfileUpdateSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.UPDATE_MY_PROFILE)),
    session: AsyncSession = Depends(get_session),
) -> Profile:
    """Cập nhật hồ sơ người dùng"""
    try:
        # Lấy hồ sơ của người dùng hiện tại và cập nhật
        profile = await update_user_profile(
            user_id=current_user.id, profile_data=profile_data, session=session
        )

        logger.info(f"Cập nhật hồ sơ người dùng thành công cho người dùng {current_user.id}")
        return profile

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(
            f"Lỗi không mong muốn khi cập nhật hồ sơ người dùng: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Cập nhật hồ sơ người dùng thất bại.",
                "action": "Vui lòng thử lại sau.",
            },
        )