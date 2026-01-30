from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.api.services.user_auth import user_auth_service
from backend.app.api.routes.auth.deps import get_current_user
from backend.app.auth.schema import ChangePasswordSchema
from backend.app.auth.utils import verify_password
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Đổi mật khẩu người dùng",
    description="Endpoint cho phép người dùng đã đăng nhập đổi mật khẩu hiện tại của họ.",
)
async def change_password(
    password_data: ChangePasswordSchema,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Đổi mật khẩu người dùng đã đăng nhập"""
    try:
        # Thay đổi mật khẩu
        await user_auth_service.change_user_password(
            current_user.id,
            password_data,
            session
        )
        logger.info(f"Người dùng {current_user.email} thay đổi mật khẩu thành công.")
        return {
            "status": "success",
            "message": "Mật khẩu đã được thay đổi thành công.",
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Đổi mật khẩu cho người dùng {current_user.email} thất bại: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể thay đổi mật khẩu.",
                "action": "Vui lòng thử lại sau.",
            },
        )