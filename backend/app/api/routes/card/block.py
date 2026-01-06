from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.card import block_virtual_card
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.card_blocked import send_card_blocked_email
from backend.app.virtual_card.schema import CardBlockSchema

logger = get_logger()
router = APIRouter(prefix="/virtual-card", tags=["Virtual Card"])


@router.post(
    "/{card_id}/block",
    status_code=status.HTTP_200_OK,
    description="Block a virtual card. Can be performed by card owner or account executive",
)
async def block_card(
    card_id: UUID,
    block_data: CardBlockSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    # API khóa thẻ ảo (chủ thẻ hoặc Account Executive đều có quyền)
    try:
        # Gọi service xử lý khóa thẻ
        card, card_owner = await block_virtual_card(
            card_id=card_id,
            block_data=block_data.model_dump(),
            blocked_by=current_user.id,
            session=session,
        )

        try:
            # Gửi email thông báo khóa thẻ cho chủ thẻ
            await send_card_blocked_email(
                email=card_owner.email,
                full_name=card_owner.full_name,
                card_type=card.card_type.value,
                masked_card_number=card.masked_card_number,
                block_reason=(
                    str(card.block_reason.value) if card.block_reason else ""
                ),
                block_reason_description=(
                    str(card.block_reason_description)
                    if card.block_reason_description
                    else ""
                ),
                blocked_at=card.blocked_at or datetime.now(timezone.utc),
            )
        except Exception as email_error:
            # Không rollback nếu gửi email thất bại
            logger.error(f"Failed to send card blocked email: {email_error}")

        # Trả về kết quả khóa thẻ
        return {
            "status": "success",
            "message": "Card blocked successfully",
            "data": {
                "card_id": str(card.id),
                "status": card.card_status.value,
                "block_reason": (
                    card.block_reason.value if card.block_reason else ""
                ),
                "blocked_at": (
                    card.blocked_at.isoformat() if card.blocked_at else None
                ),
            },
        }

    except HTTPException:
        # Ném lại lỗi HTTP đã được xử lý ở service layer
        raise

    except Exception as e:
        # Lỗi hệ thống không xác định
        logger.error(f"Failed to block virtual card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to block virtual card",
            },
        )
