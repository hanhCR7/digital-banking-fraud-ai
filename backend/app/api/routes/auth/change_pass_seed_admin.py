from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.api.services.user_auth import user_auth_service
from backend.app.auth.schema import ChangeInitialPasswordSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post(
    "/change-initial-password",
    status_code=status.HTTP_200_OK,
    summary="Đổi mật khẩu lần đầu",
    description="Bắt buộc đổi mật khẩu cho user được seed ban đầu (không cần JWT)."
)
async def change_password(
    data: ChangeInitialPasswordSchema,
    session: AsyncSession = Depends(get_session),
):
    """Đổi mật khẩu người dùng đã đăng nhập"""
    try:
        # Thay đổi mật khẩu
        await user_auth_service.change_initial_password(
            data.user_id,
            data,
            session
        )
        logger.info(f"Người dùng {data.user_id} thay đổi mật khẩu thành công.")
        return {
            "status": "success",
            "message": "Mật khẩu đã được thay đổi thành công.",
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Đổi mật khẩu cho người dùng {data.user_id} thất bại: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể thay đổi mật khẩu.",
                "action": "Vui lòng thử lại sau.",
            },
        )