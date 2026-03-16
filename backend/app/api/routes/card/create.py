from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.card import create_virtual_card
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.card_created import send_card_created_email
from backend.app.virtual_card.schema import (
    VirtualCardCreateSchema,
    VirtualCardReadSchema,
)
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema

logger = get_logger()
router = APIRouter(prefix="/virtual-card", tags=["Virtual Card"])


@router.post(
    "/create",
    response_model=VirtualCardReadSchema,
    status_code=status.HTTP_201_CREATED,
    description="Tạo thẻ ảo mới. Thẻ sẽ ở trạng thái pending cho đến khi được kích hoạt bởi Account Executive.",
)
async def create_card(
    card_data: VirtualCardCreateSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.CREATE_VIRTUAL_CARD)),
    session: AsyncSession = Depends(get_session),
) -> VirtualCardReadSchema:
    # API tạo thẻ ảo mới cho người dùng
    try:
        # Gọi service xử lý tạo thẻ ảo
        card, user, bank_account = await create_virtual_card(
            user_id=current_user.id,
            bank_account_id=card_data.bank_account_id,
            card_data=card_data.model_dump(exclude={"bank_account_id"}),
            session=session,
        )

        try:
            # Gửi email thông báo tạo thẻ thành công cho người dùng
            await send_card_created_email(
                email=user.email,
                full_name=user.full_name,
                card_type=card.card_type.value,
                currency=card.currency.value,
                masked_card_number=card.masked_card_number,
                name_on_card=card.name_on_card,
                daily_limit=card.daily_limit,
                monthly_limit=card.monthly_limit,
                expiry_date=card.expiry_date.strftime("%m/%Y"),
            )
        except Exception as email_error:
            # Không rollback nếu gửi email thất bại
            logger.error(f"Gửi thông báo tạo thẻ thất bại: {email_error}")

        # Trả về thông tin thẻ vừa tạo (ẩn các dữ liệu nhạy cảm)
        return VirtualCardReadSchema.model_validate(card)

    except HTTPException:
        # Ném lại các lỗi HTTP đã được xử lý ở service layer
        raise

    except Exception as e:
        # Lỗi hệ thống không xác định
        logger.error(f"Tạo thẻ thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Tạo thẻ thất bại.",
            },
        )
