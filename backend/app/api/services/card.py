import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.core.config import settings
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.core.logging import get_logger
from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from backend.app.transaction.models import Transaction
from backend.app.virtual_card.enums import VirtualCardStatusEnum
from backend.app.virtual_card.models import VirtualCard
from backend.app.virtual_card.utils import (
    generate_card_expiry_date,
    generate_cvv,
    generate_visa_card_number,
)

logger = get_logger()


async def create_virtual_card(
    user_id: UUID, bank_account_id: UUID, card_data: dict, session: AsyncSession
) -> tuple[VirtualCard, User, BankAccount]:
    """
    Tạo thẻ ảo mới cho người dùng từ tài khoản ngân hàng hợp lệ
    """
    try:
        # Lấy thông tin tài khoản ngân hàng và chủ sở hữu
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.id == bank_account_id, BankAccount.user_id == user_id)
        )
        result = await session.exec(statement)
        account_user = result.first()

        # Tài khoản không tồn tại hoặc không thuộc người dùng
        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Tài khoản ngân hàng không tìm thấy hoặc không thuộc người dùng",
                },
            )

        bank_account, user = account_user

        # Chỉ cho phép tạo thẻ với tài khoản đang hoạt động
        if bank_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Tài khoản ngân hàng không hoạt động"},
            )

        # Kiểm tra tiền tệ của thẻ phải trùng với tài khoản ngân hàng
        card_currency = card_data.get("currency")
        if card_currency != bank_account.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tiền tệ của thẻ phải trùng với tài khoản ngân hàng",
                },
            )

        # Loại bỏ các field không cho phép client truyền vào
        cleaned_data = card_data.copy()
        cleaned_data.pop("card_number", None)
        cleaned_data.pop("card_status", None)
        cleaned_data.pop("is_active", None)
        cleaned_data.pop("cvv_hash", None)
        cleaned_data.pop("available_balance", None)
        cleaned_data.pop("total_topped_up", None)
        cleaned_data.pop("card_metadata", None)

        # Sinh số thẻ Visa hợp lệ
        card_number = generate_visa_card_number()

        # Nếu không truyền expiry_date thì tự động generate
        if not cleaned_data.get("expiry_date"):
            expiry_date = generate_card_expiry_date()
            cleaned_data["expiry_date"] = expiry_date.date()

        # Khởi tạo object VirtualCard
        card = VirtualCard(
            **cleaned_data,
            card_number=card_number,
            bank_account_id=bank_account_id,
            card_status=VirtualCardStatusEnum.Pending,
            is_active=True,
            available_balance=0.0,
            total_topped_up=0.0,
            last_top_up_date=datetime.now(timezone.utc),
            card_metadata={
                "created_by": str(user.id),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Lưu thẻ vào database
        session.add(card)
        await session.commit()
        await session.refresh(card)

        return card, user, bank_account

    except HTTPException:
        # Rollback khi có lỗi nghiệp vụ
        await session.rollback()
        raise
    except Exception as e:
        # Rollback và log lỗi hệ thống
        await session.rollback()
        logger.error(f"Không thể tạo thẻ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Không thể tạo thẻ"},
        )


async def block_virtual_card(
    card_id: UUID, block_data: dict, blocked_by: UUID, session: AsyncSession
) -> tuple[VirtualCard, User]:
    """
    Khóa thẻ ảo theo yêu cầu người dùng hoặc quản trị
    """
    try:
        # Lấy thông tin thẻ và chủ thẻ
        statement = (
            select(VirtualCard, User)
            .select_from(VirtualCard)
            .join(BankAccount)
            .join(User)
            .where(VirtualCard.id == card_id)
        )
        result = await session.exec(statement)
        card_data = result.first()

        # Không tìm thấy thẻ
        if not card_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Thẻ không tìm thấy"},
            )

        card, card_owner = card_data

        # Không cho phép khóa thẻ đã bị khóa
        if card.card_status == VirtualCardStatusEnum.Blocked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Thẻ đã bị khóa"},
            )

        # Cập nhật trạng thái khóa thẻ
        block_time = datetime.now(timezone.utc)
        card.card_status = VirtualCardStatusEnum.Blocked
        card.block_reason = block_data["block_reason"]
        card.block_reason_description = block_data["block_reason_description"]
        card.blocked_by = blocked_by
        card.blocked_at = block_time

        # Cập nhật metadata
        if not card.card_metadata:
            card.card_metadata = {}

        card.card_metadata.update(
            {
                "blocked_at": block_time.isoformat(),
                "blocked_by": str(blocked_by),
                "block_reason": block_data["block_reason"].value,
            }
        )

        session.add(card)
        await session.commit()
        await session.refresh(card)

        return card, card_owner

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Không thể khóa thẻ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Không thể khóa thẻ"},
        )


async def top_up_virtual_card(
    card_id: UUID,
    account_number: str,
    amount: float,
    description: str,
    session: AsyncSession,
) -> tuple[VirtualCard, Transaction]:
    """
    Nạp tiền từ tài khoản ngân hàng vào thẻ ảo
    """
    try:
        # Lấy thông tin thẻ và tài khoản ngân hàng
        statement = (
            select(VirtualCard, BankAccount)
            .join(BankAccount)
            .where(
                VirtualCard.id == card_id,
                BankAccount.account_number == account_number,
            )
        )
        result = await session.exec(statement)
        card_account = result.first()

        # Không tìm thấy thẻ hoặc tài khoản
        if not card_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Thẻ hoặc tài khoản ngân hàng không tìm thấy",
                },
            )

        card, bank_account = card_account

        # Kiểm tra trạng thái thẻ và tài khoản
        if card.card_status != VirtualCardStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Thẻ không hoạt động"},
            )

        if bank_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Tài khoản ngân hàng không hoạt động"},
            )

        # Kiểm tra số dư
        if Decimal(str(bank_account.balance)) < Decimal(str(amount)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Số dư trong tài khoản không đủ",
                },
            )

        # Kiểm tra tiền tệ
        if card.currency != bank_account.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tiền tệ của thẻ phải trùng với tài khoản ngân hàng",
                },
            )
        formatted_amount = f"{settings.MIN_TOPUP_AMOUNT:,.0f}"
        if Decimal(str(amount)) <= Decimal(str(settings.MIN_TOPUP_AMOUNT)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": f"Số tiền nạp phải lớn hơn {formatted_amount} VNĐ",
                },
            )

        # Sinh reference giao dịch
        reference = f"TOPUP{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(bank_account.balance))
        balance_after = balance_before - Decimal(str(amount))
        current_time = datetime.now(timezone.utc)

        # Tạo transaction nạp tiền
        transaction = Transaction(
            amount=Decimal(str(amount)),
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Transfer,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Completed,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=bank_account.id,
            sender_id=bank_account.user_id,
            completed_at=current_time,
            transaction_metadata={
                "top_up_type": "virtual_card",
                "card_id": str(card.id),
                "card_last_four": card.last_four_digits,
                "currency": card.currency.value,
            },
        )

        # Cập nhật số dư
        bank_account.balance = balance_after
        card.available_balance += amount
        card.total_topped_up += amount
        card.last_top_up_date = current_time

        session.add(transaction)
        session.add(bank_account)
        session.add(card)
        await session.commit()

        await session.refresh(transaction)
        await session.refresh(card)

        return card, transaction

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Không thể nạp tiền vào thẻ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Không thể nạp tiền vào thẻ"},
        )


async def activate_virtual_card(
    card_id: UUID, activated_by: UUID, session: AsyncSession
) -> tuple[VirtualCard, User, str]:
    """
    Kích hoạt thẻ ảo (chỉ Account Executive được phép)
    """
    try:
        # Lấy thẻ, tài khoản ngân hàng và chủ thẻ
        statement = (
            select(VirtualCard, BankAccount, User)
            .select_from(VirtualCard)
            .join(BankAccount)
            .join(User)
            .where(VirtualCard.id == card_id)
        )
        result = await session.exec(statement)
        card_data = result.first()

        # Không tìm thấy thẻ
        if not card_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Thẻ không tìm thấy"},
            )

        card, bank_account, card_owner = card_data

        # Không cho phép kích hoạt thẻ đã active
        if card.card_status == VirtualCardStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Thẻ đã được kích hoạt"},
            )

        # Sinh CVV mới khi kích hoạt
        new_cvv, cvv_hash = generate_cvv()
        card.card_status = VirtualCardStatusEnum.Active
        card.cvv_hash = cvv_hash

        # Cập nhật metadata
        if not card.card_metadata:
            card.card_metadata = {}

        card.card_metadata.update(
            {
                "activated_by": str(activated_by),
                "activated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        session.add(card)
        await session.commit()
        await session.refresh(card)

        # Trả về CVV một lần duy nhất cho client
        return card, card_owner, new_cvv

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Không thể kích hoạt thẻ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Không thể kích hoạt thẻ"},
        )


async def delete_virtual_card(
    card_id: UUID, user_id: UUID, session: AsyncSession
) -> dict:
    """
    Xóa mềm thẻ ảo theo yêu cầu người dùng
    """
    try:
        # Kiểm tra thẻ có thuộc người dùng không
        statement = (
            select(VirtualCard, BankAccount)
            .join(BankAccount)
            .where(VirtualCard.id == card_id, BankAccount.user_id == user_id)
        )
        result = await session.exec(statement)
        card_account = result.first()

        if not card_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Thẻ không tìm thấy hoặc không thuộc người dùng",
                },
            )

        card, _ = card_account

        # Không cho phép xóa nếu đã yêu cầu thẻ vật lý
        if card.physical_card_requested_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Không thể xóa thẻ nếu đã yêu cầu thẻ vật lý",
                },
            )

        # Không cho phép xóa nếu còn số dư
        if card.available_balance > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Không thể xóa thẻ nếu còn số dư",
                    "action": "Vui lòng rút số dư trước",
                },
            )

        deletion_time = datetime.now(timezone.utc)

        # Lưu lịch sử xóa vào metadata
        existing_metadata = card.card_metadata or {}
        card.card_metadata = {
            **existing_metadata,
            "deleted_at": deletion_time.isoformat(),
            "deletion_reason": "user_requested",
            "deleted_by": str(user_id),
            "card_status_before_deletion": card.card_status.value,
            "deletion_timestamp": deletion_time.timestamp(),
        }

        # Xóa mềm bằng cách đổi trạng thái
        card.card_status = VirtualCardStatusEnum.Inactive
        card.is_active = False

        session.add(card)
        await session.commit()
        await session.refresh(card)

        logger.info(f"Thẻ {card_id} đã được xóa")

        return {
            "status": "success",
            "message": "Thẻ đã được xóa",
            "deleted_at": deletion_time,
        }

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Không thể xóa thẻ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Không thể xóa thẻ"},
        )
