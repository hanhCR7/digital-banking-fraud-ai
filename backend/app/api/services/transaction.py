import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlmodel import any_, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.auth.utils import generate_otp
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.bank_account.utils import calculate_conversion
from backend.app.transaction.utils import mark_transaction_failed
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionFailureReason,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from backend.app.transaction.models import Transaction


logger = get_logger()

async def process_deposit(
    *,
    amount: Decimal,
    account_id: uuid.UUID,
    teller_id: uuid.UUID,
    description: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, User]:
    """Xử lý nghiệp vụ nạp tiền vào tài khoản."""
    try:
        # Lấy tài khoản và chủ tài khoản
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.id == account_id)
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account not found"},
            )

        account, account_owner = account_user
        # Chỉ cho phép nạp tiền vào tài khoản đang hoạt động
        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Account is not active"},
            )
        # Sinh mã tham chiếu giao dịch
        reference = f"DEP{uuid.uuid4().hex[:8].upper()}"
        # Tính số dư trước và sau khi nạp tiền
        balance_before = Decimal(str(account.balance))
        balance_after = balance_before + amount
        # Tạo bản ghi giao dịch nạp tiền
        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Deposit,
            transaction_category=TransactionCategoryEnum.Credit,
            status=TransactionStatusEnum.Pending,
            balance_before=balance_before,
            balance_after=balance_after,
            receiver_account_id=account_id,
            receiver_id=account_owner.id,
            processed_by=teller_id,
            transaction_metadata={
                "currency": account.currency,
                "account_number": account.account_number,
            },
        )
        # Ghi thông tin teller xử lý giao dịch
        teller = await session.get(User, teller_id)
        if teller:
            if transaction.transaction_metadata is None:
                transaction.transaction_metadata = {}
            transaction.transaction_metadata["teller_name"] = teller.full_name
            transaction.transaction_metadata["teller_email"] = teller.email
        # Cập nhật số dư tài khoản
        account.balance = float(balance_after)
        # Hoàn tất giao dịch
        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)
        session.add(transaction)
        session.add(account)
        await session.commit()
        return transaction, account, account_owner
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to process deposit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to process deposit"},
        )
async def initiate_transfer(
    *,
    sender_id: uuid.UUID,
    sender_account_id: uuid.UUID,
    receiver_account_number: str,
    amount: Decimal,
    description: str,
    security_answer: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, BankAccount, User, User]:
    """Khởi tạo giao dịch chuyển tiền giữa hai tài khoản."""
    try:
        # Không cho phép chuyển tiền vào tài khoản của chính mình
        receiver_self_check = await session.exec(
            select(BankAccount).where(
                BankAccount.account_number == receiver_account_number,
                BankAccount.user_id == sender_id,
            )
        )
        if receiver_self_check.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Cannot transfer to your own account",
                },
            )
        # Lấy tài khoản và user người gửi
        sender_stmt = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.id == sender_account_id,
                BankAccount.user_id == sender_id,
            )
        )
        # Thực thi truy vấn
        sender_result = await session.exec(sender_stmt)
        sender_data = sender_result.first()
        if not sender_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Sender account not found"},
            )
        # Phân tách dữ liệu người gửi
        sender_account, sender = sender_data
        # Kiểm tra trạng thái tài khoản và câu trả lời bảo mật
        if sender_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Sender account is not active"},
            )
        # Kiểm tra câu trả lời bảo mật
        if security_answer != sender.security_answer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Incorrect security answer"},
            )
        # Lấy tài khoản và user người nhận
        receiver_stmt = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.account_number == receiver_account_number)
        )
        # Thực thi truy vấn
        receiver_result = await session.exec(receiver_stmt)
        receiver_data = receiver_result.first()
        # Phân tách dữ liệu người nhận
        if not receiver_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Receiver account not found"},
            )
        receiver_account, receiver = receiver_data
        # Kiểm tra trạng thái tài khoản người nhận
        if receiver_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Receiver account is not active"},
            )
        # Kiểm tra số dư tài khoản người gửi
        if Decimal(str(sender_account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insufficient balance"},
            )
        # Xử lý chuyển đổi tiền tệ nếu khác loại tiền
        if sender_account.currency != receiver_account.currency:
            converted_amount, exchange_rate, conversion_fee = calculate_conversion(
                amount,
                sender_account.currency,
                receiver_account.currency,
            )
        else:
            converted_amount = amount
            exchange_rate = Decimal("1.0")
            conversion_fee = Decimal("0")
        # Sinh mã tham chiếu giao dịch
        reference = f"TRF{uuid.uuid4().hex[:8].upper()}"
        # Tạo bản ghi giao dịch chuyển tiền
        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Transfer,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Pending,
            balance_before=Decimal(str(sender_account.balance)),
            balance_after=Decimal(str(sender_account.balance)) - amount,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            sender_id=sender.id,
            receiver_id=receiver.id,
            transaction_metadata={
                "conversion_rate": str(exchange_rate),
                "conversion_fee": str(conversion_fee),
                "original_amount": str(amount),
                "converted_amount": str(converted_amount),
                "from_currency": sender_account.currency.value,
                "to_currency": receiver_account.currency.value,
            },
        )
        # Sinh OTP xác nhận giao dịch
        otp = generate_otp()
        sender.otp = otp
        sender.otp_expiry_time = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRATION_MINUTES
        )
        session.add(transaction)
        session.add(sender)
        await session.commit()
        await session.refresh(transaction)
        return transaction, sender_account, receiver_account, sender, receiver
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to initiate transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to initiate transfer"},
        )
    
async def complete_transfer(
    *, reference: str, otp: str, session: AsyncSession
) -> tuple[Transaction, BankAccount, BankAccount, User, User]:
    """
    Hoàn tất giao dịch chuyển tiền sau khi người dùng xác thực OTP.
    Quy trình xử lý:
    1. Kiểm tra giao dịch tồn tại và đang ở trạng thái Pending
    2. Lấy thông tin người gửi, người nhận và tài khoản liên quan
    3. Xác thực OTP và thời hạn OTP
    4. Kiểm tra trạng thái tài khoản và số dư
    5. Thực hiện trừ tiền người gửi, cộng tiền người nhận
    6. Cập nhật trạng thái giao dịch và lưu kết quả
    """
    try:
        # 1. Lấy giao dịch theo reference, chỉ xử lý giao dịch Pending
        stmt = select(Transaction).where(
            Transaction.reference == reference,
            Transaction.status == TransactionStatusEnum.Pending,
        )
        result = await session.exec(stmt)
        transaction = result.first()
        # Không tìm thấy giao dịch hợp lệ
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Transfer not found"},
            )
        # 2. Lấy thông tin tài khoản và người dùng liên quan
        sender_account = await session.get(BankAccount, transaction.sender_account_id)
        receiver_account = await session.get(
            BankAccount, transaction.receiver_account_id
        )
        sender = await session.get(User, transaction.sender_id)
        receiver = await session.get(User, transaction.receiver_id)
        # Kiểm tra dữ liệu liên quan có đầy đủ không
        if not all([sender_account, receiver_account, sender, receiver]):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INVALID_ACCOUNT,
                details={
                    "sender_account_found": bool(sender_account),
                    "receiver_account_found": bool(receiver_account),
                    "sender_found": bool(sender),
                    "receiver_found": bool(receiver),
                },
                session=session,
                error_message="Account information not found",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account information not found"},
            )
        # 3. Xác thực OTP người gửi
        if not sender or not sender.otp or sender.otp != otp:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INVALID_OTP,
                details={"provided_otp": otp},
                session=session,
                error_message="Invalid OTP",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Invalid OTP"},
            )
        # Kiểm tra OTP hết hạn
        if (
            not sender.otp_expiry_time
            or datetime.now(timezone.utc) > sender.otp_expiry_time
        ):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.OTP_EXPIRED,
                details={
                    "expiry_time": (
                        sender.otp_expiry_time.isoformat()
                        if sender.otp_expiry_time
                        else None
                    ),
                    "current_time": datetime.now(timezone.utc).isoformat(),
                },
                session=session,
                error_message="OTP has expired",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "OTP has expired"},
            )
        # 4. Kiểm tra trạng thái tài khoản
        if sender_account and sender_account.account_status != AccountStatusEnum.Active:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.ACCOUNT_INACTIVE,
                details={"account": "sender"},
                session=session,
                error_message="Sender account is no longer active",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Sender account is no longer active",
                },
            )
        if (
            receiver_account
            and receiver_account.account_status != AccountStatusEnum.Active
        ):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.ACCOUNT_INACTIVE,
                details={"account": "receiver"},
                session=session,
                error_message="Receiver account is no longer active",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Receiver account is no longer active",
                },
            )
        if not sender_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Sendwer account not found"},
            )
        # 5. Kiểm tra số dư người gửi
        if Decimal(str(sender_account.balance)) < transaction.amount:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INSUFFICIENT_BALANCE,
                details={
                    "required_amount": str(transaction.amount),
                    "available_balance": str(sender_account.balance),
                    "shortfall": str(
                        transaction.amount - Decimal(str(sender_account.balance))
                    ),
                },
                session=session,
                error_message="Insufficient balance",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insufficient balance"},
            )
        # 6. Kiểm tra metadata giao dịch (dùng cho quy đổi tiền tệ)
        if not transaction.transaction_metadata:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SYSTEM_ERROR,
                details={"error": "Missing transaction metadata"},
                session=session,
                error_message="System error: Missing transaction metadata",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "System error: Missing transaction metadata",
                },
            )

        if not transaction.transaction_metadata:
            raise ValueError("Transaction metadata is missing")

        converted_amount = Decimal(transaction.transaction_metadata["converted_amount"])
        # Thực hiện trừ tiền người gửi
        sender_account.balance = float(
            Decimal(str(sender_account.balance)) - transaction.amount
        )

        if not receiver_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Receiver account not found"},
            )
        # 7. Cập nhật số dư tài khoản người nhận
        receiver_account.balance = float(
            Decimal(str(receiver_account.balance)) + converted_amount
        )
        # 8. Cập nhật trạng thái giao dịch
        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)
        # Xóa OTP sau khi giao dịch thành công
        sender.otp = ""
        sender.otp_expiry_time = None
        # 9. Lưu thay đổi vào database
        session.add(transaction)
        session.add(sender_account)
        session.add(receiver_account)
        session.add(sender)
        await session.commit()
        # Refresh dữ liệu sau commit
        await session.refresh(transaction)
        await session.refresh(sender_account)
        await session.refresh(receiver_account)
        await session.refresh(sender)
        await session.refresh(receiver)

        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Receiver not found"},
            )
        return transaction, sender_account, receiver_account, sender, receiver
    # Xử lý lỗi nghiệp vụ (HTTPException)
    except HTTPException:
        await session.rollback()
        raise
    # Xử lý lỗi hệ thống không mong muốn
    except Exception as e:
        if transaction:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SYSTEM_ERROR,
                details={"error": str(e)},
                session=session,
                error_message="A system error occurred",
            )
        await session.rollback()
        logger.error(f"Failed to complete transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to complete the transfer"},
        )
async def process_withdrawal(
    *,
    account_number: str,
    amount: Decimal,
    username: str,
    description: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, User]:
    """Xử lý nghiệp vụ rút tiền từ tài khoản."""
    try:
        # Lấy tài khoản và user theo số tài khoản + username
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.account_number == account_number,
                User.username == username,
            )
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account or username not found"},
            )

        account, user = account_user

        # Kiểm tra tài khoản hoạt động
        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Account is not active"},
            )

        # Kiểm tra đủ số dư
        if Decimal(str(account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insufficient balance"},
            )

        # Sinh mã tham chiếu giao dịch
        reference = f"WTH{uuid.uuid4().hex[:8].upper()}"

        # Tính số dư trước / sau
        balance_before = Decimal(str(account.balance))
        balance_after = balance_before - amount

        # Tạo giao dịch rút tiền
        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Withdrawal,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Completed,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=account.id,
            sender_id=user.id,
            completed_at=datetime.now(timezone.utc),
            transaction_metadata={
                "currency": account.currency.value,
                "account_number": account.account_number,
                "withdrawal_method": "cash",
            },
        )

        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        # Hoàn tất giao dịch và cập nhật số dư
        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        account.balance = float(balance_after)

        session.add(account)
        await session.commit()
        await session.refresh(account)

        return transaction, account, user

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to process withdrawal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to process withdrawal"},
        )

async def get_user_transactions(
    user_id: uuid.UUID,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    transaction_type: TransactionTypeEnum | None = None,
    transaction_category: TransactionCategoryEnum | None = None,
    transaction_status: TransactionStatusEnum | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> tuple[list[Transaction], int]:
    """Lấy lịch sử giao dịch của người dùng (có phân trang & filter)."""
    try:
        # Lấy danh sách tài khoản của user
        account_stmt = select(BankAccount.id).where(BankAccount.user_id == user_id)
        result = await session.exec(account_stmt)
        account_ids = [account_id for account_id in result.all()]

        if not account_ids:
            return [], 0

        # Query giao dịch liên quan đến user hoặc các tài khoản của user
        base_query = select(Transaction).where(
            or_(
                Transaction.sender_id == user_id,
                Transaction.receiver_id == user_id,
                Transaction.sender_account_id == any_(account_ids),
                Transaction.receiver_account_id == any_(account_ids),
            )
        )

        # Áp dụng các điều kiện filter
        if start_date:
            base_query = base_query.where(Transaction.created_at >= start_date)
        if end_date:
            base_query = base_query.where(Transaction.created_at <= end_date)
        if transaction_type:
            base_query = base_query.where(
                Transaction.transaction_type == transaction_type
            )
        if transaction_category:
            base_query = base_query.where(
                Transaction.transaction_category == transaction_category
            )
        if transaction_status:
            base_query = base_query.where(Transaction.status == transaction_status)
        if min_amount is not None:
            base_query = base_query.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            base_query = base_query.where(Transaction.amount <= max_amount)

        # Sắp xếp theo thời gian mới nhất
        base_query = base_query.order_by(desc(Transaction.created_at))

        # Đếm tổng số giao dịch
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await session.exec(count_query)
        total_count = total.first() or 0

        # Lấy danh sách giao dịch theo phân trang
        transactions = await session.exec(base_query.offset(skip).limit(limit))
        transaction_list = list(transactions.all())

        # Load quan hệ & gắn thông tin đối tác giao dịch
        for transaction in transaction_list:
            await session.refresh(
                transaction,
                ["sender", "receiver", "sender_account", "receiver_account"],
            )

            transaction.transaction_metadata = transaction.transaction_metadata or {}

            # Xác định đối tác giao dịch
            if transaction.sender_id == user_id:
                if transaction.receiver:
                    transaction.transaction_metadata["counterparty_name"] = (
                        transaction.receiver.full_name
                    )
                if transaction.receiver_account:
                    transaction.transaction_metadata["counterparty_account"] = (
                        transaction.receiver_account.account_number
                    )
            else:
                if transaction.sender:
                    transaction.transaction_metadata["counterparty_name"] = (
                        transaction.sender.full_name
                    )
                if transaction.sender_account:
                    transaction.transaction_metadata["counterparty_account"] = (
                        transaction.sender_account.account_number
                    )

        return transaction_list, total_count

    except Exception as e:
        logger.error(f"Error fetching user transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to fetch transaction history",
                "action": "Please try again later",
            },
        )
