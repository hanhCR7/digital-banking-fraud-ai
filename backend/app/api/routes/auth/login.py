from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.api.services.user_auth import user_auth_service
from backend.app.api.services.user_role import user_role_service
from backend.app.api.services.permissions import permission_service
from backend.app.auth.schema import LoginRequestSchema, OTPVerifyRequestSchema
from backend.app.auth.utils import create_jwt_token, set_auth_cookies
from backend.app.core.db import get_session
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login/request-otp", status_code=status.HTTP_200_OK)
async def requets_login_otp(
    login_data: LoginRequestSchema,
    session: AsyncSession = Depends(get_session)
):
    """Đăng nhập bằng mã otp được gửi qua mail. Chỉ gửi OTP khi email tồn tại và mật khẩu đúng."""
    try:
        user = await user_auth_service.get_user_by_email(login_data.email, session)
        # Email không tồn tại trong CSDL → trả lỗi, không gửi OTP
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Email hoặc mật khẩu không đúng.",
                    "action": "Vui lòng kiểm tra lại email và mật khẩu rồi thử lại.",
                },
            )
        # Kiểm tra user có bị khóa TK hay không
        await user_auth_service.check_user_lockout(user, session)
        # Kiểm tra mật khẩu
        if not await user_auth_service.verify_user_password(
            login_data.password, user.hashed_password
        ):
            # Tăng số lần nhập sai
            await user_auth_service.increment_failed_login_attempts(user, session)
            remaining_attempts = (
                settings.LOGIN_ATTEMPTS - user.failed_login_attempts
            )
            if remaining_attempts > 0:
                error_message = (
                    f"Thông tin đăng nhập không hợp lệ. Bạn còn {remaining_attempts} "
                    f"lần thử trước khi tài khoản của bạn bị tạm thời khóa."
                )
            else:
                error_message = (
                    "Thông tin đăng nhập không hợp lệ. Tài khoản của bạn đã bị tạm thời khóa do "
                    f"quá nhiều lần đăng nhập thất bại. Vui lòng thử lại sau {settings.LOCKOUT_DURATION_MINUTES} phút."
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": error_message,
                    "action": "Vui lòng kiểm tra lại email và mật khẩu rồi thử lại",
                    "remaining_attempts": remaining_attempts,
                },
            )
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Bạn chưa đăng ký tài khoản!",
                    "action": "Vui lòng đăng ký tài khoản trước",
                },
            )
        # Kiểm tra tài khoản đã kích hoạt chưa
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản của bạn chưa được kích hoạt",
                    "action": "Vui lòng kích hoạt tài khoản trước",
                },
            )
        # Đặt lại trạng thái người dùng trước khi gửi OTP
        await user_auth_service.reset_user_state(
            user, session, clear_otp=True, log_action=True
        )
        # Tạo và gửi mã OTP (chỉ khi email tồn tại + mật khẩu đúng)
        await user_auth_service.generate_and_save_otp(user, session)
        return {
            "message": "Mã OTP đã được gửi đến email của bạn. Vui lòng kiểm tra hộp thư."
        }
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Không thể xử lý yêu cầu OTP đăng nhập: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Không thể xử lý yêu cầu OTP đăng nhập"},
        )

@router.post("/login/verify-otp", status_code=status.HTTP_200_OK)
async def verify_login_otp(
    verify_data: OTPVerifyRequestSchema,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Xác thực mã OTP để login"""
    try:
        # Xác thực mã OTP
        user = await user_auth_service.verify_login_otp(
            verify_data.email, verify_data.otp, session
        )
        if user.must_change_password:
            return{
                "message": "Bạn phải đổi mật khẩu trước khi sử dụng hệ thống.",
                "require_password_change": True,
                "user_id": user.id
            }
        # Đặt lại trạng thái người dùng sau khi xác thực thành công
        await user_auth_service.reset_user_state(
            user, session, clear_otp=True, log_action=True
        )
        # Lấy role và permisson của user
        role = await user_role_service.get_user_role(session, user.id)
        if not role:
            logger.warning(f"Người dùng không tồn tại với vai trò: {role}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Vai trò không tồn tại.",
                    "action": "Vui lòng đăng nhập lại!",
                },
            )
        permissions = await permission_service.get_user_permission(session, user.id)
        if not permissions:
            logger.warning(f"Người dùng không tồn tại với quyền: {list[permissions]}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Quyền không tồn tại.",
                    "action": "Vui lòng đăng nhập lại!",
                },
            )
        # Tạo và thiết lập cookie xác thực
        access_token = create_jwt_token(
            user.id, 
            role=role,
        )
        refresh_token = create_jwt_token(user.id, type=settings.COOKIE_REFRESH_NAME)
        set_auth_cookies(response, access_token, refresh_token)

        return {
            "message": "Đăng nhập thành công!",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "id_no": user.id_no,
                "role": role,
            },
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Không thể xác thực OTP đăng nhập: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể xác thực OTP.",
                "action": "Vui lòng thử lại sau.",
            },
        )
