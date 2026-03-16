from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import review_flagged_transaction
from backend.app.role.schema import RoleChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import TransactionReviewSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema


# Khởi tạo logger cho module
logger = get_logger()

# Router cho các API liên quan đến transaction
router = APIRouter(prefix="/transaction", tags=["Transaction"])


@router.post(
    "/{transaction_id}/review",
    status_code=status.HTTP_200_OK,
    description="Xem xét giao dịch bị gắn cờ. Chỉ dành cho nhân viên quản lý tài khoản.",
)
async def review_transaction(
    transaction_id: UUID,
    review_data: TransactionReviewSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.REVIEW_TRANSACTION)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Review thủ công một giao dịch đã bị AI Fraud Detection đánh dấu."""
    try:

        # Gọi service xử lý review giao dịch bị AI flag
        result = await review_flagged_transaction(
            transaction_id=transaction_id,
            reviewer_id=current_user.id,
            is_fraud=review_data.is_fraud,
            notes=review_data.notes,
            approve_transaction=review_data.approve_transaction,
            session=session,
        )

        # Trả về kết quả review cho client
        return result

    except HTTPException:
        # Bắt và trả lại các lỗi nghiệp vụ đã được xử lý trước đó
        raise

    except Exception as e:
        # Log lỗi hệ thống không mong muốn
        logger.error(f"Lỗi khi xem xét giao dịch: {e}")

        # Trả về lỗi chung cho client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi khi xem xét giao dịch.",
                "action": "Vui lòng thử lại sau.",
            },
        )
