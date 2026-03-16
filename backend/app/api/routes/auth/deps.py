from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.core.config import settings
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()


def _extract_access_token(request: Request) -> str | None:
    """Lấy access token từ cookie hoặc header Authorization: Bearer (SPA thường gửi Bearer)."""
    token = request.cookies.get(settings.COOKIE_ACCESS_NAME)
    if token:
        return token
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Xác thực người dùng từ access token (cookie hoặc Authorization: Bearer)."""
    access_token = _extract_access_token(request)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Không xác thực được.",
                "action": "Vui lòng đăng nhập để truy cập tài nguyên.",
            },
        )

    try:
        payload = jwt.decode(
            access_token,
            settings.SIGNING_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != settings.COOKIE_ACCESS_NAME:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Token không hợp lệ.",
                    "action": "Vui lòng đăng nhập để truy cập tài nguyên.",
                },
            )

        from backend.app.api.services.user_auth import user_auth_service

        user = await user_auth_service.get_user_by_id(payload["id"], session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Người dùng không tồn tại.",
                    "action": "Vui lòng đăng nhập lại.",
                },
            )
        await user_auth_service.validate_user_status(user)
        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Token đã hết hạn.",
                "action": "Vui lòng đăng nhập lại.",
            },
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Token không hợp lệ.",
                "action": "Vui lòng đăng nhập lại.",
            },
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Xác thực thất bại.",
                "action": "Vui lòng thử lại sau.",
            },
        )

# Định nghĩa kiểu chú thích cho người dùng hiện tại
CurrentUser = Annotated[User, Depends(get_current_user)]