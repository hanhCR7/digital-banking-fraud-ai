from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import update_next_of_kin
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.schema import NextOfKinReadSchema, NextOfKinUpdateSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()
router = APIRouter(prefix="/next-of-kin", tags=["Next of Kin"])


@router.patch(
    "/{next_of_kin_id}",
    response_model=NextOfKinReadSchema,
    status_code=status.HTTP_200_OK,
    description="Cập nhật thông tin người thân (Next of Kin) của người dùng hiện tại. Chỉ cập nhật các trường được cung cấp.",
)
async def update_next_of_kin_route(
    next_of_kin_id: UUID,
    update_data: NextOfKinUpdateSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.UPDATE_NEXT_OF_KIN)),
    session: AsyncSession = Depends(get_session),
) -> NextOfKinReadSchema:
    """API cập nhật thông tin người thân (Next of Kin) của người dùng hiện tại."""
    try:
        # Gọi service cập nhật Next of Kin, đảm bảo thuộc quyền user hiện tại
        next_of_kin = await update_next_of_kin(
            user_id=current_user.id,
            next_of_kin_id=next_of_kin_id,
            update_data=update_data,
            session=session,
        )
        logger.info(f"Người dùng {current_user.email} đã cập nhật người thân: {next_of_kin_id}")
        return NextOfKinReadSchema.model_validate(next_of_kin)

    except HTTPException as http_ex:
        logger.warning(
            f"Cập nhật người thân (Next of Kin) thất bại cho người dùng {current_user.email}: {http_ex.detail}"
        )
        raise http_ex
    except Exception as e:
        logger.error(f"Cập nhật người thân (Next of Kin) thất bại: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Cập nhật người thân (Next of Kin) thất bại.",
                "action": "Vui lòng thử lại sau.",
            },
        )