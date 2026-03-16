import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.user_auth import user_auth_service
from backend.app.api.services.user_role import user_role_service
from backend.app.api.services.permissions import permission_service
from backend.app.auth.utils import create_jwt_token, set_auth_cookies
from backend.app.core.config import settings
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_access_token(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(None, alias=settings.COOKIE_REFRESH_NAME),
) -> dict:
    """Tạo access_token mới khi hết hạn sử dụng"""
    try:
        # CHeck refresh token
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Không có refresh token được cung cấp.",
                    "action": "Vui lòng đăng nhập lại!",
                },
            )
        try:
            # Decode refresh token
            payload = jwt.decode(
                refresh_token, settings.SIGNING_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Refresh token đã hết hạn.",
                    "action": "Vui lòng đăng nhập lại!",
                },
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Refresh token không hợp lệ.",
                    "action": "Vui lòng đăng nhập lại!",
                },
            )
        # Kiểm tra loại token
        if payload.get("type") != settings.COOKIE_REFRESH_NAME:
            logger.warning(
                f"Invalid token type. Expected {settings.COOKIE_REFRESH_NAME}, "
                f"got {payload.get('type')}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Loại token không hợp lệ.",
                    "action": "Vui lòng đăng nhập lại!",
                },
            )
        # Lấy user từ payload
        user = await user_auth_service.get_user_by_id(payload["id"], session)
        if not user:
            logger.warning(f"User not found for ID: {payload['id']}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Người dùng không tồn tại.",
                    "action": "Vui lòng đăng nhập lại!",
                },
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
        # Kiểm tra trạng thái user
        await user_auth_service.validate_user_status(user)
        # Tạo access token mới
        new_access_token = create_jwt_token(
            user.id, 
            role=role
        )
        # Đặt access token vào cookie
        set_auth_cookies(response, new_access_token)

        logger.info(f"Refresh access token thành công cho người dùng {user.email}")
        return {
            "message": "Access token đã được refresh thành công.",
            "access_token": new_access_token,
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể refresh token.",
                "action": "Vui lòng thử lại sau.",
            },
        )