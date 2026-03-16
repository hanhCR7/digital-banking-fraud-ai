from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import process_withdrawal
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.withdrawal_alert import send_withdrawal_alert
from backend.app.transaction.models import IdempotencyKey
from backend.app.transaction.schema import WithdrawalRequestSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()
router = APIRouter(prefix="/transaction", tags=["Transaction"])

def validate_uuid4(value: str) -> str:
    """Kiểm tra chuỗi có phải UUID v4 hợp lệ hay không."""
    try:
        uuid_obj = UUID(value, version=4)
        if str(uuid_obj) != value.lower():
            raise ValueError("Không phải là UUID v4 hợp lệ")
        return value
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Khóa idempotency không hợp lệ",
            },
        )
@router.post("/withdraw", status_code=status.HTTP_201_CREATED)
async def create_withdrawal(
    withdrawal_data: WithdrawalRequestSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.CREATE_WITHDRAWAL)),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(
        description="Khóa idempotency cho yêu cầu rút tiền"
    ),
):
    """API rút tiền (có hỗ trợ idempotency)."""
    try:
        # Validate idempotency key (UUID v4)
        idempotency_key = validate_uuid4(idempotency_key)
        if not idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Khóa idempotency không hợp lệ.",
                },
            )

        # Kiểm tra request đã được xử lý trước đó hay chưa
        existing_key_result = await session.exec(
            select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.endpoint == "/withdraw",
                IdempotencyKey.expires_at > datetime.now(timezone.utc),
            )
        )
        existing_key = existing_key_result.first()

        if existing_key:
            # Trả lại response đã cache
            return {
                "status": "success",
                "message": "Lấy dữ liệu từ bộ nhớ đệm.",
                "data": existing_key.response_body,
            }

        # Gọi service xử lý nghiệp vụ rút tiền
        transaction, account, user = await process_withdrawal(
            account_number=withdrawal_data.account_number,
            amount=withdrawal_data.amount,
            username=withdrawal_data.username,
            description=withdrawal_data.description,
            session=session,
        )

        # Gửi email thông báo rút tiền (side-effect)
        try:
            await send_withdrawal_alert(
                email=user.email,
                full_name=user.full_name,
                amount=transaction.amount,
                account_name=account.account_name,
                account_number=account.account_number or "Unknown",
                currency=account.currency.value,
                desciption=transaction.description,
                transaction_date=transaction.completed_at or transaction.created_at,
                reference=transaction.reference,
                balance=Decimal(str(account.balance)),
            )
        except Exception as e:
            logger.error(f"Gửi thông báo rút tiền thất bại: {e}")

        # Response trả về cho client
        response = {
            "status": "success",
            "message": "Rút tiền thành công.",
            "data": {
                "transaction_id": str(transaction.id),
                "reference": transaction.reference,
                "amount": str(transaction.amount),
                "balance": str(transaction.balance_after),
                "status": transaction.status.value,
            },
        }

        # Lưu idempotency key để tránh xử lý trùng request
        idempotency_record = IdempotencyKey(
            key=idempotency_key,
            user_id=user.id,
            endpoint="/withdraw",
            response_code=status.HTTP_201_CREATED,
            response_body=response,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(idempotency_record)
        await session.commit()

        return response

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Hoàn tất rút tiền thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Hoàn tất rút tiền thất bại."},
        )
