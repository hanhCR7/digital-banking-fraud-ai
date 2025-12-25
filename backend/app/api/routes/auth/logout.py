from fastapi import APIRouter, HTTPException, Response, status
from backend.app.auth.utils import delete_auth_cookies
from backend.app.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/auth", tags=["Athentication"])

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response)-> dict:
    """Đăng Xuất bằng cách xóa cookie xác thực"""
    try:
        # Xoá cookie xác thực
        delete_auth_cookies(response)
        logger.info("User logged out successfully")
        return{ "message": "Logged out successfully" }
    except Exception as e:
        logger.error(f"Failed to log out user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to log out user",
                "action": "Please try again later",
            },
        )