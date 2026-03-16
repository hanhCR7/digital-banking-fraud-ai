from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import process_deposit
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.deposit_alert import send_deposit_alert
from backend.app.transaction.enums import TransactionTypeEnum
from backend.app.transaction.schema import DepositRequestSchema

logger = get_logger()

router = APIRouter(prefix="/transaction", tags=["Transaction"])


@router.post("/deposit", status_code=status.HTTP_201_CREATED)
async def create_deposit(
    deposit_data: DepositRequestSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.CREATE_DEPOSIT)),
    session: AsyncSession = Depends(get_session),
):
    """API nạp tiền vào tài khoản (chỉ dành cho teller)."""
    try:
        # Gọi service xử lý nghiệp vụ nạp tiền
        transaction, account, account_owner = await process_deposit(
            amount=deposit_data.amount,
            account_id=deposit_data.account_id,
            teller_id=current_user.id,
            description=deposit_data.description,
            session=session,
        )

        # Đảm bảo tài khoản có số tài khoản hợp lệ
        if not account.account_number:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Yêu cầu cung cấp số tài khoản!"},
            )

        # Gửi email thông báo nạp tiền (side-effect)
        try:
            await send_deposit_alert(
                email=account_owner.email,
                full_name=account_owner.full_name,
                action=TransactionTypeEnum.Deposit.value,
                amount=transaction.amount,
                account_name=account.account_name,
                account_number=account.account_number,
                currency=account.currency.value,
                description=transaction.description,
                transaction_date=transaction.completed_at or transaction.created_at,
                reference=transaction.reference,
                balance=transaction.balance_after,
            )
        except Exception as email_error:
            # Lỗi gửi email không ảnh hưởng kết quả giao dịch
            logger.error(f"Gửi thông báo giao dịch thất bại: {email_error}")

        # Trả kết quả giao dịch
        return {
            "status": "success",
            "message": "Giao dịch nạp tiền đã được xử lý thành công!",
            "data": {
                "transaction_id": transaction.id,
                "reference": transaction.reference,
                "amount": transaction.amount,
                "balance": transaction.balance_after,
                "status": transaction.status,
            },
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Xử lý giao dịch nạp tiền thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Xử lý giao dịch nạp tiền thất bại"},
        )
