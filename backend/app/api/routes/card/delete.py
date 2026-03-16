from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.card import delete_virtual_card
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.virtual_card.schema import CardDeleteResponseSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()
router = APIRouter(prefix="/virtual-card", tags=["Virtual Card"])


@router.delete(
    "/{card_id}",
    response_model=CardDeleteResponseSchema,
    status_code=status.HTTP_200_OK,
    description="Xóa mềm thẻ ảo. Thẻ phải có số dư bằng 0 và không có yêu cầu thẻ vật lý",
)
async def delete_card(
    card_id: UUID,
    current_user = Depends(require_permission(PermissionChoicesSchema.DELETE_VIRTUAL_CARD)),
    session: AsyncSession = Depends(get_session),
) -> CardDeleteResponseSchema:
    # API xóa mềm thẻ ảo theo yêu cầu người dùng
    try:
        # Gọi service xử lý xóa thẻ ảo
        result = await delete_virtual_card(
            card_id=card_id,
            user_id=current_user.id,
            session=session,
        )

        # Trả về kết quả xóa thẻ
        return CardDeleteResponseSchema(
            status="success",
            message="Thẻ ảo đã được xóa mềm.",
            deleted_at=result["deleted_at"],
        )

    except HTTPException:
        # Ném lại lỗi HTTP đã được xử lý ở service layer
        raise

    except Exception as e:
        # Lỗi hệ thống không xác định
        logger.error(f"Xóa mềm thẻ thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Xóa mềm thẻ thất bại.",
            },
        )
