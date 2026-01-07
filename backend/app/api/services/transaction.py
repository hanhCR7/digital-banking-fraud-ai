from typing import Any
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
from backend.app.core.tasks.statement import generate_statement_pdf
from backend.app.core.utils.number_format import format_currency
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
from backend.app.core.ai.enums import AIReviewStatusEnum
from backend.app.core.ai.models import TransactionRiskScore
from backend.app.core.ai.service import TransactionAIService
from backend.app.core.services.transfer_alert import send_transfer_alert
from backend.app.core.services.withdrawal_alert import send_withdrawal_alert


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
        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        # Phân tích rủi ro giao dịch bằng AI
        ai_service = TransactionAIService(session)
        risk_analysis = await ai_service.analyze_transaction(transaction, sender_id)
        # Nếu giao dịch bị AI đánh dấu rủi ro
        if risk_analysis.get("needs_review", False):
            await ai_service.handle_flagged_transaction(transaction, risk_analysis)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "This transaction has been "
                    "flagged as potentially fraudulent. An "
                    "account executive will review the "
                    "transaction, before its either "
                    "approved or rejected",
                    "risk_analysis": {
                        "risk_score": risk_analysis["risk_score"],
                        "risk_factors": risk_analysis["risk_factors"],
                    },
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
    """
    Xử lý nghiệp vụ rút tiền từ tài khoản.

    Flow:
    1. Xác thực tài khoản & người dùng
    2. Kiểm tra trạng thái tài khoản
    3. Kiểm tra số dư
    4. Tạo transaction Pending
    5. Phân tích rủi ro bằng AI
    6. Nếu an toàn → trừ tiền & hoàn tất giao dịch
    7. Commit & refresh dữ liệu
    """
    try:
        # 1. Lấy tài khoản và user theo account_number + username
        stmt = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.account_number == account_number,
                User.username == username,
            )
        )
        result = await session.exec(stmt)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account or username not found"},
            )

        account, user = account_user

        # 2. Kiểm tra trạng thái tài khoản
        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Account is not active"},
            )

        # 3. Kiểm tra số dư
        balance_before = Decimal(str(account.balance))
        if balance_before < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insufficient balance"},
            )

        balance_after = balance_before - amount

        # 4. Tạo giao dịch Pending
        reference = f"WTH{uuid.uuid4().hex[:8].upper()}"

        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Withdrawal,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Pending,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=account.id,
            sender_id=user.id,
            transaction_metadata={
                "currency": account.currency.value,
                "account_number": account.account_number,
                "withdrawal_method": "cash",
            },
        )

        session.add(transaction)
        await session.flush()  # Chưa commit, chỉ lấy ID

        # 5. Phân tích rủi ro bằng AI
        ai_service = TransactionAIService(session)
        risk_analysis = await ai_service.analyze_transaction(transaction, user.id)

        if risk_analysis.get("needs_review", False):
            await ai_service.handle_flagged_transaction(transaction, risk_analysis)
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "This transaction has been flagged as potentially fraudulent "
                               "and is pending manual review",
                    "risk_analysis": {
                        "risk_score": risk_analysis["risk_score"],
                        "risk_factors": risk_analysis["risk_factors"],
                    },
                },
            )

        # 6. Trừ tiền & hoàn tất giao dịch
        account.balance = float(balance_after)
        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        session.add(account)
        session.add(transaction)

        # 7. Commit & refresh
        await session.commit()
        await session.refresh(transaction)
        await session.refresh(account)

        return transaction, account, user

    # Xử lý lỗi nghiệp vụ
    except HTTPException:
        await session.rollback()
        raise

    # Xử lý lỗi hệ thống
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
async def get_user_statement_data(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
) -> tuple[dict[str, Any], list[Transaction]]:
    """Lấy dữ liệu người dùng và giao dịch để tạo sao kê."""
    try:
        # Lấy thông tin user
        user_stmt = select(User).where(User.id == user_id)
        result = await session.exec(user_stmt)
        user = result.first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Chuẩn hóa họ tên hiển thị
        full_name = (
            f"{user.first_name} "
            f"{user.middle_name + ' ' if user.middle_name else ''}"
            f"{user.last_name}"
        ).title().strip()

        user_info = {
            "username": user.username,
            "email": user.email,
            "full_name": full_name,
        }

        # Lấy danh sách giao dịch trong khoảng thời gian
        txn_stmt = (
            select(Transaction)
            .where(
                (Transaction.sender_id == user_id)
                | (Transaction.receiver_id == user_id),
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
            )
            .order_by(desc(Transaction.created_at))
        )

        txn_result = await session.exec(txn_stmt)
        transactions = txn_result.all()

        return user_info, list(transactions)

    except Exception as e:
        logger.error(f"Failed to get statement data for user {user_id}: {e}")
        raise
async def prepare_statement_data(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
    account_number: str | None = None,
) -> dict:
    """
    Chuẩn bị dữ liệu user, tài khoản và giao dịch để tạo sao kê.
    """
    try:
        # 1. Lấy thông tin user
        user_query = select(User).where(User.id == user_id)
        result = await session.exec(user_query)
        user = result.first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        full_name = (
            f"{user.first_name} "
            f"{user.middle_name + ' ' if user.middle_name else ''}"
            f"{user.last_name}"
        ).strip()

        # 2. Xác định danh sách tài khoản
        if account_number:
            account_query = select(BankAccount).where(
                BankAccount.account_number == account_number,
                BankAccount.user_id == user_id,
            )
            account_result = await session.exec(account_query)
            account = account_result.first()

            if not account:
                raise ValueError("Account not found or does not belong to user")

            accounts = [account]
        else:
            accounts_query = select(BankAccount).where(BankAccount.user_id == user_id)
            accounts_result = await session.exec(accounts_query)
            accounts = accounts_result.all()

        if not accounts:
            raise ValueError("User has no bank accounts")

        # 3. Chuẩn hóa thông tin tài khoản (FORMAT TIỀN)
        account_details = []
        for acc in accounts:
            if not acc.account_number:
                continue

            account_details.append(
                {
                    "account_number": acc.account_number,
                    "account_name": acc.account_name,
                    "account_type": acc.account_type.value,
                    "currency": acc.currency.value,
                    "balance": format_currency(
                        acc.balance,
                        acc.currency.value,
                    ),
                }
            )

        account_ids = [acc.id for acc in accounts]

        # 4. Lấy giao dịch đã hoàn tất
        transactions_query = (
            select(Transaction)
            .where(
                or_(
                    Transaction.sender_account_id == any_(account_ids),
                    Transaction.receiver_account_id == any_(account_ids),
                ),
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
                Transaction.status == TransactionStatusEnum.Completed,
            )
            .order_by(desc(Transaction.created_at))
        )

        result = await session.exec(transactions_query)
        transactions = result.all()

        # 5. Chuẩn hóa dữ liệu giao dịch (FORMAT TIỀN)
        transaction_data: list[dict] = []

        for txn in transactions:
            sender_account = (
                await session.get(BankAccount, txn.sender_account_id)
                if txn.sender_account_id
                else None
            )
            receiver_account = (
                await session.get(BankAccount, txn.receiver_account_id)
                if txn.receiver_account_id
                else None
            )

            # Xác định loại tiền hiển thị
            currency = (
                sender_account.currency.value
                if sender_account
                else receiver_account.currency.value
                if receiver_account
                else "USD"
            )

            transaction_data.append(
                {
                    "reference": txn.reference,
                    "date": txn.created_at.strftime("%Y-%m-%d"),
                    "description": txn.description,
                    "transaction_type": txn.transaction_type.value,
                    "transaction_category": txn.transaction_category.value,
                    "amount": format_currency(txn.amount, currency),
                    "balance_after": format_currency(
                        txn.balance_after, currency
                    ),
                    "sender_account": (
                        sender_account.account_number if sender_account else None
                    ),
                    "receiver_account": (
                        receiver_account.account_number if receiver_account else None
                    ),
                    "metadata": txn.transaction_metadata or {},
                }
            )

        # 6. Dữ liệu tổng hợp cho PDF
        return {
            "user": {
                "username": user.username,
                "email": user.email,
                "full_name": full_name,
            },
            "accounts": account_details,
            "transactions": transaction_data,
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
            "is_single_account": bool(account_number),
        }

    except ValueError as e:
        logger.error(f"Error preparing statement data: {e}")
        raise
    except Exception as e:
        logger.error(f"Error preparing statement data: {e}")
        raise
async def generate_user_statement(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
    account_number: str | None = None,
) -> dict:
    """Khởi tạo quy trình tạo sao kê cho người dùng."""
    try:
        # Chuẩn bị dữ liệu sao kê
        statement_data = await prepare_statement_data(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            session=session,
            account_number=account_number,
        )

        # Sinh ID sao kê
        statement_id = str(uuid.uuid4())

        # Gửi task tạo PDF chạy nền
        task = generate_statement_pdf.delay(
            statement_data=statement_data, statement_id=statement_id
        )

        return {
            "status": "pending",
            "message": "Statement generation initiated",
            "statement_id": statement_id,
            "task_id": task.id,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error(f"Failed to initiate statement generation: {e}")
        raise
async def review_flagged_transaction(
    transaction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    is_fraud: bool,
    approve_transaction: bool,
    notes: str | None,
    session: AsyncSession,
) -> dict:
    """
    Duyệt thủ công giao dịch bị AI đánh dấu nghi ngờ gian lận.

    Flow nghiệp vụ:
    1. Lấy giao dịch + risk score
    2. Kiểm tra giao dịch có đang ở trạng thái FLAGGED không
    3. Reviewer xác nhận fraud hoặc không
    4. Nếu được approve → hoàn tất giao dịch
    5. Ghi metadata lịch sử duyệt
    6. Commit kết quả
    """
    try:
        # 1. Lấy giao dịch và thông tin risk score liên quan
        query = (
            select(Transaction, TransactionRiskScore)
            .join(TransactionRiskScore)
            .where(Transaction.id == transaction_id)
        )

        result = await session.exec(query)
        transaction_data = result.first()

        if not transaction_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Transaction not found"},
            )

        transaction, risk_score = transaction_data

        # 2. Chỉ cho phép review giao dịch đang bị FLAGGED
        if transaction.ai_review_status != AIReviewStatusEnum.FLAGGED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Transaction is not flagged for review",
                    "current_status": transaction.ai_review_status,
                },
            )

        # 3. Reviewer xác nhận giao dịch có gian lận hay không
        if is_fraud:
            # Reviewer xác nhận là gian lận
            transaction.ai_review_status = AIReviewStatusEnum.CONFIRMED_FRAUD
            transaction.status = TransactionStatusEnum.Failed

            risk_score.is_confirmed_fraud = True
            risk_score.reviewed_by = reviewer_id

        else:
            # Reviewer xác nhận giao dịch an toàn
            transaction.ai_review_status = AIReviewStatusEnum.CLEARED

        # 4. Nếu giao dịch được approve → thực hiện hoàn tất
        if approve_transaction:
            if transaction.transaction_type == TransactionTypeEnum.Transfer:
                await _complete_approved_transfer(transaction, session)

            elif transaction.transaction_type == TransactionTypeEnum.Withdrawal:
                await _complete_approved_withdrawal(transaction, session)

        # 5. Lưu metadata lịch sử duyệt fraud
        if not transaction.transaction_metadata:
            transaction.transaction_metadata = {}

        transaction.transaction_metadata["fraud_review"] = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": str(reviewer_id),
            "is_fraud": is_fraud,
            "notes": notes,
        }

        # 6. Commit kết quả
        session.add(transaction)
        session.add(risk_score)
        await session.commit()

        return {
            "status": "success",
            "message": "Transaction reviewed successfully",
            "transaction_id": str(transaction_id),
            "is_fraud": is_fraud,
            "review_status": transaction.ai_review_status,
            "risk_score": risk_score.risk_score,
        }
    # Lỗi nghiệp vụ
    except HTTPException:
        raise
    # Lỗi hệ thống
    except Exception as e:
        logger.error(f"Error reviewing transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to review transaction",
                "action": "Please try again later",
            },
        )
async def _complete_approved_transfer(transaction: Transaction, session: AsyncSession):
    """Hoàn tất giao dịch CHUYỂN TIỀN đã được reviewer chấp thuận sau khi bị AI flag."""
    try:
        # 1. Load thông tin người gửi, người nhận và các tài khoản liên quan
        sender = await session.get(User, transaction.sender_id)
        receiver = await session.get(User, transaction.receiver_id)

        sender_account = await session.get(BankAccount, transaction.sender_account_id)
        receiver_account = await session.get(
            BankAccount, transaction.receiver_account_id
        )

        # 2. Validate dữ liệu bắt buộc (user / account)
        # Nếu thiếu bất kỳ entity nào → dừng xử lý
        if not sender:
            raise ValueError("Sender not found")
        if not receiver:
            raise ValueError("Receiver not found")
        if not sender_account:
            raise ValueError("Sender account not found")
        if not receiver_account:
            raise ValueError("Receiver account not found")

        # 3. Kiểm tra metadata giao dịch (bắt buộc với chuyển tiền quốc tế)
        if not transaction.transaction_metadata:
            raise ValueError("Transaction metadata is missing")

        converted_amount_str = transaction.transaction_metadata.get("converted_amount")

        if not converted_amount_str:
            raise ValueError("Converted amount is missing from metadata")

        # 4. Parse số tiền đã quy đổi (string → Decimal)
        try:
            converted_amount = Decimal(converted_amount_str)
        except (TypeError, ValueError):
            raise ValueError(
                f"Invalid converted amount format:{converted_amount_str}"
            )
        # 5. Kiểm tra số dư hiện tại của người gửi
        current_sender_balance = Decimal(str(sender_account.balance))

        if current_sender_balance < transaction.amount:
            raise ValueError("Insufficient balance for transfer")

        try:

            # 6. Thực hiện cập nhật số dư hai tài khoản
            sender_account.balance = float(
                current_sender_balance - transaction.amount
            )
            receiver_account.balance = float(
                Decimal(str(receiver_account.balance)) + converted_amount
            )

            # 7. Đánh dấu giao dịch hoàn tất
            transaction.status = TransactionStatusEnum.Completed
            transaction.completed_at = datetime.now(timezone.utc)

            # 8. Persist thay đổi vào database
            session.add(sender_account)
            session.add(receiver_account)
            session.add(transaction)

            await session.commit()

            # 9. Refresh entity sau khi commit
            await session.refresh(transaction)
            await session.refresh(sender_account)
            await session.refresh(receiver_account)

            # 10. Gửi thông báo giao dịch cho người gửi & người nhận

            try:
                await send_transfer_alert(
                    sender_email=sender.email,
                    receiver_email=receiver.email,
                    sender_name=sender.full_name,
                    receiver_name=receiver.full_name,
                    sender_account_number=sender_account.account_number or "Uknown",
                    receiver_account_number=receiver_account.account_number
                    or "Unknown",
                    amount=transaction.amount,
                    converted_amount=converted_amount,
                    sender_currency=sender_account.currency,
                    receiver_currency=receiver_account.currency,
                    exchange_rate=Decimal(
                        transaction.transaction_metadata.get("conversion_rate", "1"),
                    ),
                    conversion_fee=Decimal(
                        transaction.transaction_metadata.get("conversion_fee", "0"),
                    ),
                    description=transaction.description,
                    reference=transaction.reference,
                    transaction_date=transaction.completed_at
                    or transaction.created_at,
                    sender_balance=Decimal(str(sender_account.balance)),
                    receiver_balance=Decimal(str(receiver_account.balance)),
                )
                logger.info(
                    f"Successfully sent transfer approval notificatoin "
                    f"for transaction {transaction.reference}"
                )
            except Exception as e:
                # Lỗi gửi email chỉ log, không rollback giao dịch
                logger.error(
                    f"Failed to send transfer approval notification: {e}"
                )

        except Exception as e:
            # 11. Lỗi trong quá trình cập nhật số dư hoặc commit
            await session.rollback()
            raise ValueError(f"Failed to process transfer: {str(e)}")
    except ValueError as e:
        # 12. Lỗi validation / nghiệp vụ
        # → rollback và đánh dấu giao dịch thất bại
        await session.rollback()
        logger.error(
            f"Validation error in _complete_approved_transfer: {e}"
        )
        transaction.status = TransactionStatusEnum.Failed
        transaction.transaction_metadata = {
            **(transaction.transaction_metadata or {}),
            "failure_reason": str(e),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        session.add(transaction)
        await session.commit()
        raise
    except Exception as e:
        # 13. Lỗi hệ thống không mong muốn
        await session.rollback()
        logger.error(
            f"Unexpected error in _complete_approved_transfer: {e}"
        )
        raise
async def _complete_approved_withdrawal(
    transaction: Transaction, session: AsyncSession
):
    """Hoàn tất giao dịch RÚT TIỀN đã được reviewer chấp thuận sau khi bị AI flag."""
    try:
        # Lấy thông tin người dùng thực hiện rút tiền
        user = await session.get(User, transaction.sender_id)

        # Lấy tài khoản nguồn dùng để rút tiền
        account = await session.get(BankAccount, transaction.sender_account_id)

        # Validate dữ liệu bắt buộc
        if not user:
            raise ValueError("User not found")
        if not account:
            raise ValueError("Account not found")

        # Kiểm tra số dư tài khoản trước khi rút
        if Decimal(str(account.balance)) < transaction.amount:
            raise ValueError("Insufficient balance for withdrawal")

        try:
            # Trừ tiền khỏi số dư tài khoản
            account.balance = float(
                Decimal(str(account.balance)) - transaction.amount
            )

            # Cập nhật trạng thái giao dịch thành hoàn tất
            transaction.status = TransactionStatusEnum.Completed
            transaction.completed_at = datetime.now(timezone.utc)

            # Lưu thay đổi vào database
            session.add(account)
            session.add(transaction)

            await session.commit()

            # Refresh dữ liệu sau khi commit
            await session.refresh(transaction)
            await session.refresh(account)

            try:
                # Gửi thông báo rút tiền thành công cho người dùng
                await send_withdrawal_alert(
                    email=user.email,
                    full_name=user.full_name,
                    amount=transaction.amount,
                    account_name=account.account_name,
                    account_number=account.account_number or "Unknown",
                    currency=account.currency.value,
                    desciption=transaction.description,
                    transaction_date=transaction.completed_at
                    or transaction.created_at,
                    reference=transaction.reference,
                    balance=Decimal(str(account.balance)),
                )
                logger.info(
                    f"Successfully sent withdrawal approval notificatoin "
                    f"for transaction {transaction.reference}"
                )
            except Exception as e:
                # Lỗi gửi notification không ảnh hưởng đến giao dịch
                logger.error(
                    f"Failed to send withdrawal approval notification: {e}"
                )

        except Exception as e:
            # Lỗi xảy ra trong quá trình xử lý rút tiền
            await session.rollback()
            raise ValueError(f"Failed to process withdrawal: {str(e)}")

    except ValueError as e:
        # Lỗi nghiệp vụ / validation
        await session.rollback()
        logger.error(
            f"Validation error in _complete_approved_withdrawal: {e}"
        )

        # Đánh dấu giao dịch thất bại và ghi lại lý do
        transaction.status = TransactionStatusEnum.Failed
        transaction.transaction_metadata = {
            **(transaction.transaction_metadata or {}),
            "failure_reason": str(e),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        session.add(transaction)
        await session.commit()
        raise

    except Exception as e:
        # Lỗi hệ thống không mong muốn
        await session.rollback()
        logger.error(
            f"Unexpected error in _complete_approved_transfer: {e}"
        )
        raise
async def get_user_risk_history(
    user_id: uuid.UUID,
    session: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_risk_score: float | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """Lấy lịch sử đánh giá rủi ro giao dịch của một người dùng"""
    try:
        # Tạo query cơ sở:
        # - Lấy giao dịch của user
        # - Join với bảng TransactionRiskScore
        base_query = (
            select(Transaction, TransactionRiskScore)
            .join(TransactionRiskScore)
            .where(Transaction.sender_id == user_id)
        )

        # Lọc theo khoảng thời gian (nếu có)
        if start_date:
            base_query = base_query.where(
                Transaction.created_at >= start_date
            )

        if end_date:
            base_query = base_query.where(
                Transaction.created_at <= end_date
            )

        # Lọc theo điểm rủi ro tối thiểu (nếu có)
        if min_risk_score is not None:
            base_query = base_query.where(
                TransactionRiskScore.risk_score >= min_risk_score
            )

        # Sắp xếp:
        # - Giao dịch mới nhất trước
        # - Giao dịch có risk score cao ưu tiên hơn
        base_query = base_query.order_by(
            desc(Transaction.created_at),
            desc(TransactionRiskScore.risk_score),
        )

        # Đếm tổng số bản ghi (phục vụ phân trang)
        count_query = select(func.count()).select_from(
            base_query.subquery()
        )
        total_result = await session.exec(count_query)
        total_count = total_result.first() or 0

        # Áp dụng phân trang (offset / limit)
        paginated_query = base_query.offset(skip).limit(limit)

        result = await session.exec(paginated_query)
        transactions = result.all()

        # Chuẩn hóa dữ liệu trả về cho API
        history = []

        for transaction, risk_score in transactions:
            history.append(
                {
                    "transaction_id": str(transaction.id),
                    "reference": transaction.reference,
                    "amount": str(transaction.amount),
                    "created_at": transaction.created_at,
                    "risk_score": risk_score.risk_score,
                    "risk_factors": risk_score.risk_factors,
                    "review_status": transaction.ai_review_status,
                    "is_confirmed_fraud": risk_score.is_confirmed_fraud,
                    "reviewed_by": (
                        str(risk_score.reviewed_by)
                        if risk_score.reviewed_by
                        else None
                    ),
                    "review_details": (
                        transaction.transaction_metadata.get("fraud_review")
                        if transaction.transaction_metadata
                        else None
                    ),
                }
            )

        # Trả về:
        # - Danh sách lịch sử rủi ro
        # - Tổng số bản ghi (phục vụ frontend pagination)
        return history, total_count

    except Exception as e:
        # Xử lý lỗi hệ thống
        logger.error(f"Error getting risk history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to retrieve risk history",
                "action": "Please try again later",
            },
        )
