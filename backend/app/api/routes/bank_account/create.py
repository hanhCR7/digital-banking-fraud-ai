from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.bank_account import create_bank_account
from backend.app.bank_account.schema import (
    BankAccountCreateSchema,
    BankAccountReadSchema,
)
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.bank_account_created_email import (
    send_account_created_email,
)

logger = get_logger()

router = APIRouter(prefix="/bank-account", tags=["Bank Account"])


@router.post(
    "/create",
    response_model=BankAccountReadSchema,
    status_code=status.HTTP_201_CREATED,
    description=(
        "Tạo tài khoản ngân hàng mới. Yêu cầu hồ sơ cá nhân đã hoàn tất và có ít nhất một người thân (người thụ hưởng). "
        "Giới hạn: Tối đa 3 tài khoản cho mỗi người dùng."
    ),
)
async def create_account(
    account_data: BankAccountCreateSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.CREATE_ACCOUNT)),
    session: AsyncSession = Depends(get_session),
) -> BankAccountReadSchema:
    """
    API tạo tài khoản ngân hàng mới cho người dùng hiện tại.
    Người dùng phải hoàn tất KYC và không vượt quá số lượng tài khoản cho phép.
    """
    try:
        # Gọi service xử lý nghiệp vụ tạo tài khoản
        account = await create_bank_account(
            user_id=current_user.id,
            account_data=account_data,
            session=session,
        )

        # Gửi email thông báo tạo tài khoản (side-effect)
        # Việc gửi email không ảnh hưởng đến kết quả tạo tài khoản
        try:
            if not account.account_number:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "status": "error",
                        "message": "Không thể tạo số tài khoản",
                    },
                )

            await send_account_created_email(
                email=current_user.email,
                full_name=current_user.full_name,
                account_number=account.account_number,
                account_name=account.account_name,
                account_type=account.account_type.value,
                currency=account.currency.value,
                identification_type=current_user.profile.means_of_identification.value,
            )
        except Exception as e:
            logger.error(f"Gửi email thông báo tạo tài khoản thất bại: {e}")
        logger.info(f"Đã tạo tài khoản cho người dùng {current_user.email}")
        return BankAccountReadSchema.model_validate(account)

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Tạo tài khoản thất bại: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Tạo tài khoản thất bại!",
                "action": "Vui lòng thử lại sau!",
            },
        )
