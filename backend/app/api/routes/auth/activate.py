from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.user_auth import user_auth_service
from backend.app.auth.schema import AccountStatusSchema, EmailRequestSchema
from backend.app.auth.utils import create_activation_token
from backend.app.core.config import settings
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.activation_email import send_activation_email

logger = get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/activate/{token}", status_code=status.HTTP_200_OK)
async def activate_user(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await user_auth_service.activate_user_account(token, session)
        return {"message": "Tài khoản đã được kích hoạt thành công!", "email": user.email}
    except ValueError as e:
        error_msg = str(e)
        # Nếu mã token hết hạn
        if error_msg == "Mã kích hoạt đã hết hạn":
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "status": "error",
                    "message": "Liên kết kích hoạt đã hết hạn.",
                    "action": "Vui lòng yêu cầu gửi lại liên kết kích hoạt mới.",
                    "action_url": f"{settings.API_BASE_URL}{settings.API_V1_STR}/auth/resend-activation-link",
                    "email_required": True,
                },
            )
        # Mã token không hợp lệ
        elif error_msg == "Mã kích hoạt không hợp lệ":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Mã kích hoạt không hợp lệ.",
                    "action": "Vui lòng kiểm tra lại liên kết bạn đã nhấp có chính xác hay không.",
                },
            )
        # User đã được kích hoạt
        elif error_msg == "Tài khoản người dùng đã được kích hoạt":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản người dùng đã được kích hoạt.",
                    "action": "Vui lòng đăng nhập vào tài khoản của bạn.",
                },
            )
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Kích hoạt tài khoản người dùng thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Kích hoạt tài khoản người dùng thất bại.",
                "action": "Vui lòng thử lại sau.",
            },
        )


@router.post("/resend-activation-link", status_code=status.HTTP_200_OK)
async def resend_activation_link(
    email_data: EmailRequestSchema,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await user_auth_service.get_user_by_email(
            email_data.email, session, include_inactive=True
        )
        # Không tìm thấy user
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Nếu tồn tại tài khoản với email này, vui lòng kiểm tra hộp thư để nhận liên kết kích hoạt.",
                },
            )
        if user.is_active or user.account_status == AccountStatusSchema.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản người dùng đã được kích hoạt.",
                    "action": "Vui lòng đăng nhập vào tài khoản của bạn.",
                },
            )

        activation_token = create_activation_token(user.id)
        await send_activation_email(user.email, activation_token)

        return {
            "message": "Nếu tồn tại tài khoản với email này, vui lòng kiểm tra hộp thư để nhận liên kết kích hoạt."
        }
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Gửi lại liên kết kích hoạt thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Gửi lại liên kết kích hoạt thất bại.",
                "action": "Vui lòng thử lại sau hoặc liên hệ bộ phận hỗ trợ nếu sự cố vẫn tiếp diễn.",
            },
        )