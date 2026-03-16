from fastapi import APIRouter, HTTPException, Response, status
from backend.app.auth.utils import delete_auth_cookies
from backend.app.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response)-> dict:
    """Đăng Xuất bằng cách xóa cookie xác thực"""
    try:
        # Xoá cookie xác thực
        delete_auth_cookies(response)
        logger.info("Người dùng đăng xuất thành công!")
        return{ "message": "Đăng xuất thành công!" }
    except Exception as e:
        logger.error(f"Đăng xuất người dùng thất bại: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Đăng xuất người dùng thất bại",
                "action": "Vui lòng thử lại!",
            },
        )