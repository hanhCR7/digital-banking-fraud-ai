from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import delete_next_of_kin
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()
router = APIRouter(prefix="/next-of-kin", tags=["Next of Kin"])


@router.delete(
    "/{next_of_kin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Xoá người thân (Next of Kin) của người dùng hiện tại. Không thể xoá nếu đó là người thân cuối cùng.",
)
async def delete_next_of_kin_route(
    next_of_kin_id: UUID,
    current_user =  Depends(require_permission(PermissionChoicesSchema.DELETE_NEXT_OF_KIN)),
    session: AsyncSession = Depends(get_session),
) -> None:
    """API xoá người thân (Next of Kin) của người dùng hiện tại."""
    try:
        # Gọi service xoá Next of Kin, đảm bảo thuộc quyền user hiện tại
        await delete_next_of_kin(
            user_id=current_user.id, next_of_kin_id=next_of_kin_id, session=session
        )
    except HTTPException as http_ex:
        logger.warning(
            f"Xoá người thân (Next of Kin) thất bại cho người dùng {current_user.email}: {http_ex.detail}"
        )
        raise http_ex

    except Exception as e:
        logger.error(f"Xoá người thân (Next of Kin) thất bại: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Xoá người thân (Next of Kin) thất bại.",
                "action": "Vui lòng thử lại sau.",
            },
        )