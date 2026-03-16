from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.auth.schema import UserCreateSchema, UserReadSchema
from backend.app.api.services.user_auth import user_auth_service

logger = get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register",status_code=status.HTTP_201_CREATED,)
async def register_user(user_data: UserCreateSchema, session: AsyncSession = Depends(get_session)):
    try:
        if await user_auth_service.check_user_email_exists(user_data.email, session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Người dùng với email này đã tồn tại.",
            )

        if await user_auth_service.check_user_id_no_exists(user_data.id_no, session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Người dùng với số chứng minh nhân dân này đã tồn tại.",
            )

        new_user = await user_auth_service.create_user(user_data, session)
        logger.info(
            f"Người dùng {new_user.email} đã đăng ký thành công, chờ xác nhận"
        )
        return {
            "message": "Bạn đã đăng ký thành công! Vui lòng kiểm tra mail để kích hoạt tài khoản.",
            "User": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "id_no": new_user.id_no,
                "last_name": new_user.last_name,
                "first_name": new_user.first_name,
                "full_name": new_user.full_name,
            }
        }

    except HTTPException as http_ex:
        await session.rollback()
        raise http_ex
    except Exception as e:
        await session.rollback()
        logger.error(f"Đăng ký người dùng thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi máy chủ nội bộ",
        )