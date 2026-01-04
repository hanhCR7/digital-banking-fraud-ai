from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import complete_transfer, initiate_transfer
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.transfer_alert import send_transfer_alert
from backend.app.core.services.transfer_otp import send_transfer_otp_email
from backend.app.core.utils.number_format import format_currency
from backend.app.transaction.models import IdempotencyKey
from backend.app.transaction.schema import (
    TransferOTPVerificationSchema,
    TransferRequestSchema,
    TransferResponseSchema,
)

logger = get_logger()

# Router xử lý các API liên quan đến chuyển tiền giữa các tài khoản ngân hàng
router = APIRouter(prefix="/bank-account", tags=["Transactions"])


def validate_uuid4(value: str) -> str:
    """
    Kiểm tra Idempotency-Key có phải UUID v4 hợp lệ hay không.
    Idempotency-Key được dùng để đảm bảo request chuyển tiền
    không bị xử lý trùng lặp khi client gửi lại request.
    """
    try:
        # Parse và xác thực UUID v4
        uuid_obj = UUID(value, version=4)

        # So sánh lại để đảm bảo chuỗi UUID đúng định dạng chuẩn
        if str(uuid_obj) != value.lower():
            raise ValueError("Not a valid UUID v4")

        return value

    except (ValueError, AttributeError, TypeError):
        # Trả về lỗi 400 nếu Idempotency-Key không hợp lệ
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Idempotency-Key must be a valid UUID v4",
            },
        )


@router.post(
    "/transfer/initiate",
    response_model=TransferResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def initiate_money_transfer(
    transfer_data: TransferRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Header(
        description="Idempotency Key for the transfer request"
    ),
) -> TransferResponseSchema:
    """
    API khởi tạo giao dịch chuyển tiền.
    Giao dịch được tạo ở trạng thái Pending và yêu cầu xác thực OTP
    trước khi thực sự trừ / cộng tiền.
    """
    try:
        # 1. Validate Idempotency-Key để tránh xử lý trùng request
        idempotency_key = validate_uuid4(idempotency_key)

        # Idempotency-Key là bắt buộc đối với API chuyển tiền
        if not idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Idempotency-Key header is required",
                },
            )

        # 2. Kiểm tra request đã được xử lý trước đó chưa (idempotency)
        existing_key_result = await session.exec(
            select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.user_id == current_user.id,
                IdempotencyKey.endpoint == "/transfer/initiate",
                IdempotencyKey.expires_at > datetime.now(timezone.utc),
            )
        )
        existing_key = existing_key_result.first()

        # Nếu request đã tồn tại → trả lại response đã cache trước đó
        if existing_key:
            return TransferResponseSchema(
                status="success",
                message="Retrieved from cache",
                data=existing_key.response_body,
            )

        # 3. Gọi service khởi tạo giao dịch
        # - Kiểm tra nghiệp vụ
        # - Tạo transaction ở trạng thái Pending
        # - Sinh OTP cho người gửi
        transaction, sender_account, receiver_account, sender, receiver = (
            await initiate_transfer(
                sender_id=current_user.id,
                sender_account_id=transfer_data.sender_account_id,
                receiver_account_number=transfer_data.receiver_account_number,
                amount=transfer_data.amount,
                description=transfer_data.description,
                security_answer=transfer_data.security_answer,
                session=session,
            )
        )

        # 4. Gửi OTP xác nhận giao dịch cho người gửi qua email
        try:
            await send_transfer_otp_email(sender.email, sender.otp)
        except Exception as e:
            # Log lỗi gửi email nhưng không rollback giao dịch
            logger.error(f"Failed to send OTP email: {e}")

        # 5. Tạo response Pending cho client
        response = TransferResponseSchema(
            status="pending",
            message="Transfer initiated. Please check your email for OTP verification",
            data={
                "reference": transaction.reference,
                "amount": format_currency(
                    transaction.amount,
                    sender_account.currency
                ),
                "converted_amount": (
                    transaction.transaction_metadata.get("converted_amount", "N/A")
                    if transaction.transaction_metadata
                    else "N/A"
                ),
                "from_currency": (
                    transaction.transaction_metadata.get("from_currency", "N/A")
                    if transaction.transaction_metadata
                    else "N/A"
                ),
                "to_currency": (
                    transaction.transaction_metadata.get("to_currency", "N/A")
                    if transaction.transaction_metadata
                    else "N/A"
                ),
            },
        )

        # 6. Lưu Idempotency-Key cùng response để chống request trùng lặp
        idempotency_record = IdempotencyKey(
            key=idempotency_key,
            user_id=current_user.id,
            endpoint="/transfer/initiate",
            response_code=status.HTTP_202_ACCEPTED,
            response_body=response.model_dump(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(idempotency_record)
        await session.commit()

        return response

    except HTTPException as http_ex:
        # Trả lại lỗi nghiệp vụ cho client
        raise http_ex

    except Exception as e:
        # Bắt lỗi hệ thống không mong muốn
        logger.error(f"Failed to initiate transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to initiate transfer"},
        )


@router.post(
    "/transfer/complete",
    response_model=TransferResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def complete_money_transfer(
    verification_data: TransferOTPVerificationSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> TransferResponseSchema:
    """
    API hoàn tất giao dịch chuyển tiền sau khi người dùng xác thực OTP.
    """
    try:
        # 1. Gọi service hoàn tất giao dịch
        # - Xác thực OTP
        # - Trừ tiền người gửi
        # - Cộng tiền người nhận
        # - Cập nhật trạng thái transaction
        transaction, sender_account, receiver_account, sender, receiver = (
            await complete_transfer(
                reference=verification_data.transfer_reference,
                otp=verification_data.otp,
                session=session,
            )
        )

        # 2. Gửi email thông báo giao dịch thành công
        try:
            await send_transfer_alert(
                sender_email=sender.email,
                receiver_email=receiver.email,
                sender_name=sender.full_name,
                receiver_name=receiver.full_name,
                sender_account_number=sender_account.account_number or "Unknown",
                receiver_account_number=receiver_account.account_number or "Unknown",
                amount=transaction.amount,
                converted_amount=(
                    Decimal(
                        transaction.transaction_metadata.get("converted_amount", "0")
                    )
                    if transaction.transaction_metadata
                    else Decimal("0")
                ),
                sender_currency=sender_account.currency,
                receiver_currency=receiver_account.currency,
                exchange_rate=(
                    Decimal(
                        transaction.transaction_metadata.get("conversion_rate", "1")
                    )
                    if transaction.transaction_metadata
                    else Decimal("1")
                ),
                conversion_fee=(
                    Decimal(
                        transaction.transaction_metadata.get("conversion_fee", "0")
                    )
                    if transaction.transaction_metadata
                    else Decimal("0")
                ),
                description=transaction.description,
                reference=transaction.reference,
                transaction_date=transaction.completed_at or transaction.created_at,
                sender_balance=Decimal(sender_account.balance),
                receiver_balance=Decimal(receiver_account.balance),
            )
        except Exception as e:
            # Log lỗi gửi thông báo nhưng không ảnh hưởng đến kết quả giao dịch
            logger.error(f"Failed to send transfer alerts: {e}")

        # 3. Trả response giao dịch thành công cho client
        return TransferResponseSchema(
            status="success",
            message="Transfer completed successfully",
            data={
                "reference": transaction.reference,
                "amount": format_currency(
                    transaction.amount,
                    sender_account.currency
                ),
                "converted_amount": (
                    transaction.transaction_metadata.get("converted_amount", "N/A")
                    if transaction.transaction_metadata
                    else "N/A"
                ),
                "from_currency": (
                    transaction.transaction_metadata.get("from_currency", "N/A")
                    if transaction.transaction_metadata
                    else "N/A"
                ),
                "to_currency": (
                    transaction.transaction_metadata.get("to_currency", "N/A")
                    if transaction.transaction_metadata
                    else "N/A"
                ),
            },
        )

    except HTTPException as http_ex:
        # Bắt và trả lại lỗi nghiệp vụ
        raise http_ex

    except Exception as e:
        # Bắt lỗi hệ thống không mong muốn
        logger.error(f"Failed to complete transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to complete transfer"},
        )
