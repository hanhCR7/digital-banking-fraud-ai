from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import get_user_next_of_kins
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.schema import NextOfKinReadSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()
router = APIRouter(prefix="/next-of-kin", tags=["Next of Kin"])


@router.get(
    "/all",
    response_model=list[NextOfKinReadSchema],
    status_code=status.HTTP_200_OK,
    description="Lấy tất cả người thân (Next of Kin) của người dùng hiện tại",
)
async def list_next_of_kins(
    current_user = Depends(require_permission(PermissionChoicesSchema.VIEW_NEXT_OF_KIN)), session: AsyncSession = Depends(get_session)
) -> list[NextOfKinReadSchema]:
    """API lấy tất cả người thân (Next of Kin) của người dùng hiện tại."""
    try:
        # Gọi service layer để lấy danh sách người thân của user
        next_of_kins = await get_user_next_of_kins(
            user_id=current_user.id, session=session
        )
        return [NextOfKinReadSchema.model_validate(kin) for kin in next_of_kins]
    except HTTPException as http_ex:

        raise http_ex
    except Exception as e:
        logger.error(
            f"Lấy tất cả người thân (Next of Kin) thất bại: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lấy tất cả người thân (Next of Kin) thất bại.",
                "action": "Vui lòng thử lại sau.",
            },
        )