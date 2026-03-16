from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.bank_account import activate_bank_account
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
from backend.app.bank_account.schema import BankAccountReadSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.bank_account_activated_email import (
    send_account_activated_email,
)

logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])


@router.patch(
    "/{account_id}/activate",
    response_model=BankAccountReadSchema,
    status_code=status.HTTP_200_OK,
    description="Kích hoạt tài khoản ngân hàng sau khi hoàn tất xác minh KYC. "
    "Chỉ dành cho: Nhân viên phụ trách tài khoản (Account Executive).",
)
async def activate_account(
    account_id: UUID,
    current_user = Depends(require_permission(PermissionChoicesSchema.ACTIVATE_ACCOUNT)),
    session: AsyncSession = Depends(get_session),
) -> BankAccountReadSchema:
    """API kích hoạt tài khoản ngân hàng sau khi đã xác minh KYC."""
    try:
        activated_account, account_owner = await activate_bank_account(
            account_id=account_id, verified_by=current_user.id, session=session
        )
        try:
            if not activated_account.account_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"status": "error", "message": "Không tìm thấy số tài khoản"},
                )
            await send_account_activated_email(
                email=account_owner.email,
                full_name=account_owner.full_name,
                account_number=activated_account.account_number,
                account_name=activated_account.account_name,
                account_type=activated_account.account_type.value,
                currency=activated_account.currency.value,
            )
            logger.info(f"Email thông báo kích hoạt tài khoản ngân hàng đã được gửi tới {account_owner.email}")
        except Exception as email_error:
            logger.error(f"Gửi email thông báo kích hoạt tài khoản ngân hàng thất bại: {email_error}")

        logger.info(
            f"Tài khoản ngân hàng {account_id} đã được kích hoạt bởi nhân viên phụ trách tài khoản {current_user.email}"
        )

        return BankAccountReadSchema.model_validate(activated_account)

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Kích hoạt tài khoản ngân hàng thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Kích hoạt tài khoản ngân hàng thất bại"},
        )