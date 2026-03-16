from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.user_auth import user_auth_service
from backend.app.auth.schema import (
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
)
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.password_reset import send_password_reset_email

logger = get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    reset_data: PasswordResetRequestSchema, session: AsyncSession = Depends(get_session)
) -> dict:
    """Yêu cầu đặt lại pass bằng email"""
    try:
        user = await user_auth_service.get_user_by_email(
            reset_data.email, session, include_inactive=True
        )

        if user:
            await send_password_reset_email(user.email, user.id)

        return {
            "message": "Nếu có tài khoản tồn tại với email này, "
            " bạn sẽ nhận được hướng dẫn đặt lại mật khẩu sớm "
        }
    except Exception as e:
        logger.error(f"Yêu cầu đặt lại mật khẩu thất bại: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể xử lý yêu cầu đặt lại mật khẩu.",
                "action": "Vui lòng thử lại sau.",
            },
        )


@router.post("/reset-password/{token}", status_code=status.HTTP_200_OK)
async def reset_password(
    token: str,
    reset_data: PasswordResetConfirmSchema,
    session: AsyncSession = Depends(get_session),
):
    """ Đặt lại mật khẩu khi token hợp lệ"""
    try:
        # Đặt lại mật khẩu
        await user_auth_service.reset_password(
            token,
            reset_data.new_password,
            session,
        )
        return {"message": "Mật khẩu đã được đặt lại thành công."}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
                "action": "Vui lòng yêu cầu một liên kết đặt lại mật khẩu mới.",
            },
        )
    except Exception as e:

        logger.error(f"Đặt lại mật khẩu thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể đặt lại mật khẩu.",
                "action": "Vui lòng thử lại sau.",
            },
        )