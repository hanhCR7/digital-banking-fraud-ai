from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.card import activate_virtual_card
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.card_activated import send_card_activated_email
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()
router = APIRouter(prefix="/virtual-card", tags=["Virtual Card"])


@router.patch(
    "/{card_id}/activate",
    status_code=status.HTTP_200_OK,

    description="Kích hoạt thẻ ảo. Chỉ Account Executive được phép thực hiện hành động này",
)
async def activate_card(
    card_id: UUID,
    current_user = Depends(require_permission(PermissionChoicesSchema.ACTIVATE_CARD)),
    session: AsyncSession = Depends(get_session),
):
    # API kích hoạt thẻ ảo (chỉ Account Executive được phép)
    try:
        # Gọi service xử lý kích hoạt thẻ và sinh CVV mới
        card, card_owner, cvv = await activate_virtual_card(
            card_id=card_id,
            activated_by=current_user.id,
            session=session,
        )

        try:
            # Gửi email thông báo kích hoạt thẻ cho chủ thẻ
            await send_card_activated_email(
                email=card_owner.email,
                full_name=card_owner.full_name,
                card_type=card.card_type.value,
                currency=card.currency.value,
                masked_card_number=card.masked_card_number,
                cvv=cvv,  # CVV chỉ gửi 1 lần qua email
                expiry_date=card.expiry_date.strftime("%m/%Y"),
                daily_limit=card.daily_limit,
                monthly_limit=card.monthly_limit,
                available_balance=card.available_balance,
            )
        except Exception as email_error:
            # Không rollback nếu gửi email thất bại
            logger.error(f"Gửi thông báo kích hoạt thẻ thất bại: {email_error}")

        # Trả về kết quả kích hoạt thẻ
        return {
            "status": "success",
            "message": "Kích hoạt thẻ thành công.",
            "data": {
                "card_id": str(card.id),
                "status": card.card_status.value,
                "activated_at": (
                    card.card_metadata.get("activated_at")
                    if card.card_metadata
                    else None
                ),
            },
        }

    except HTTPException:
        # Ném lại lỗi HTTP đã được xử lý ở service layer
        raise

    except Exception as e:
        # Lỗi hệ thống không xác định
        logger.error(f"Kích hoạt thẻ thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Kích hoạt thẻ thất bại.",
            },
        )
