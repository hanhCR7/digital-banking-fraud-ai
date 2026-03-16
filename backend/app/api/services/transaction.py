from typing import Any, cast
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlmodel import any_, col, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.auth.models import User
from backend.app.auth.utils import generate_otp
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
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
MAX_ADMIN_LIMIT = 200
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
                detail={"status": "error", "message": "Tài khoản không tồn tại"},
            )

        account, account_owner = account_user
        # Chỉ cho phép nạp tiền vào tài khoản đang hoạt động
        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Tài khoản không hoạt động"},
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
                "type": "deposit",
                "currency": "VND",
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
        account.balance = balance_after
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
        logger.error(f"Lỗi khi nạp tiền: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi nạp tiền"},
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
                    "message": "Không thể chuyển tiền vào tài khoản của chính mình",
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
                detail={"status": "error", "message": "Tài khoản người gửi không tồn tại"},
            )
        # Phân tách dữ liệu người gửi
        sender_account, sender = sender_data
        # Kiểm tra trạng thái tài khoản và câu trả lời bảo mật
        if sender_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Tài khoản người gửi không hoạt động"},
            )
        # Kiểm tra câu trả lời bảo mật
        if security_answer != sender.security_answer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Câu trả lời bảo mật không chính xác"},
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
                detail={"status": "error", "message": "Tài khoản người nhận không tồn tại"},
            )
        receiver_account, receiver = receiver_data
        # Kiểm tra trạng thái tài khoản người nhận
        if receiver_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Tài khoản người nhận không hoạt động"},
            )
        # Kiểm tra số dư tài khoản người gửi
        if Decimal(str(sender_account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Số dư tài khoản người gửi không đủ"},
            )
        # Kiểm tra số tiền chuyển tối thiểu
        formatted_amount = f"{settings.MIN_TRANSACTION_AMOUNT:,.0f}"
        if Decimal(str(amount)) <= Decimal(str(settings.MIN_TRANSACTION_AMOUNT)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": f"Số tiền chuyển phải lớn hơn {formatted_amount} VNĐ",
                },
            )
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
                "type": "internal_transfer",
                "currency": "VND",
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
                    "message": "Giao dịch này đã bị đánh dấu là có dấu hiệu gian lận. "
                    "Một nhân viên quản lý tài khoản sẽ xem xét giao dịch "
                    "trước khi quyết định phê duyệt hoặc từ chối.",
                    "transaction_id": str(transaction.id),
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
        logger.error(f"Lỗi xảy ra khi khởi tạo giao dịch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi xảy ra khi khởi tạo giao dịch"},
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
                detail={"status": "error", "message": "Giao dịch không tồn tại"},
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
                error_message="Thông tin tài khoản không tìm thấy",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Thông tin tài khoản không tìm thấy"},
            )
        # 3. Xác thực OTP người gửi
        if not sender or not sender.otp or sender.otp != otp:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INVALID_OTP,
                details={"provided_otp": otp},
                session=session,
                error_message="Mã OTP không hợp lệ",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Mã OTP không hợp lệ"},
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
                error_message="Mã OTP đã hết hạn",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Mã OTP đã hết hạn"},
            )
        # 4. Kiểm tra trạng thái tài khoản
        if sender_account and sender_account.account_status != AccountStatusEnum.Active:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.ACCOUNT_INACTIVE,
                details={"account": "sender"},
                session=session,
                error_message="Tài khoản người gửi không còn hoạt động",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản người gửi không còn hoạt động",
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
                error_message="Tài khoản người nhận không còn hoạt động",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản người nhận không còn hoạt động",
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
                error_message="Số dư không đủ",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Số dư không đủ"},
            )
        # 6. Kiểm tra metadata giao dịch (dùng cho quy đổi tiền tệ)
        if not transaction.transaction_metadata:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SYSTEM_ERROR,
                details={"error": "Missing transaction metadata"},
                session=session,
                error_message="Lỗi hệ thống: Thieu du lieu giao dich",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Lỗi hệ thống: Thieu du lieu giao dich",
                },
            )

        if not transaction.transaction_metadata:
            raise ValueError("Transaction metadata is missing")

        converted_amount = transaction.amount
        # Thực hiện trừ tiền người gửi
        sender_account.balance -= transaction.amount
        # Kiểm tra tài khoản người nhận tồn tại
        if not receiver_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Tài khoản người nhận không tìm thấy"},
            )
        # 7. Cập nhật số dư tài khoản người nhận
        receiver_account.balance += converted_amount
        
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
                detail={"status": "error", "message": "Tài khoản người nhận không tìm thấy"},
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
                error_message="Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu.",
            )
        await session.rollback()
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu."},
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
                detail={"status": "error", "message": "Tài khoản hoặc người dùng không tìm thấy"},
            )

        account, user = account_user

        # 2. Kiểm tra trạng thái tài khoản
        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Tài khoản không còn hoạt động"},
            )

        # 3. Kiểm tra số dư
        balance_before = Decimal(str(account.balance))
        if balance_before < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Số dư không đủ"},
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
                    "message": "Giao dịch có dấu hiệu bất thường và đang chờ nhân viên kiểm tra.",
                    "risk_analysis": {
                        "risk_score": risk_analysis["risk_score"],
                        "risk_factors": risk_analysis["risk_factors"],
                    },
                },
            )

        # 6. Trừ tiền & hoàn tất giao dịch
        account.balance = balance_after
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
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu."},
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
        # Query giao dịch liên quan đến user hoặc các tài khoản của user
        if not account_ids:
            return [], 0

        base_query = select(Transaction).where(
            or_(
                Transaction.sender_id == user_id,
                Transaction.receiver_id == user_id,
                col(Transaction.sender_account_id).in_(account_ids),
                col(Transaction.receiver_account_id).in_(account_ids)
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
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu",
                "action": "Vui lòng thử lại sau",
            },
        )
async def get_all_transactions(
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
    """Lấy TẤT CẢ giao dịch trong hệ thống (có phân trang & filter)."""
    try:
        # Query tất cả giao dịch - KHÔNG filter theo user
        base_query = select(Transaction)
        
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

        # Load quan hệ
        for transaction in transaction_list:
            await session.refresh(
                transaction,
                ["sender", "receiver", "sender_account", "receiver_account"],
            )
            
            transaction.transaction_metadata = transaction.transaction_metadata or {}
            
            sender_info = []
            receiver_info = []
            
            if transaction.sender:
                sender_info.append(transaction.sender.full_name)
            if transaction.sender_account:
                sender_info.append(f"({transaction.sender_account.account_number})")
            
            if transaction.receiver:
                receiver_info.append(transaction.receiver.full_name)
            if transaction.receiver_account:
                receiver_info.append(f"({transaction.receiver_account.account_number})")
            
            # Gộp lại thành string
            transaction.transaction_metadata["counterparty_name"] = (
                f"{' '.join(sender_info) or 'N/A'} → {' '.join(receiver_info) or 'N/A'}"
            )
            transaction.transaction_metadata["counterparty_account"] = (
                f"{transaction.sender_account.account_number if transaction.sender_account else 'N/A'} → "
                f"{transaction.receiver_account.account_number if transaction.receiver_account else 'N/A'}"
            )

        return transaction_list, total_count

    except Exception as e:
        logger.error(f"Lỗi lấy tất cả giao dịch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu",
                "action": "Vui lòng thử lại sau",
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
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
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
                raise ValueError("Tài khoản không tìm thấy hoặc không thuộc người dùng")

            accounts = [account]
        else:
            accounts_query = select(BankAccount).where(BankAccount.user_id == user_id)
            accounts_result = await session.exec(accounts_query)
            accounts = accounts_result.all()

        if not accounts:
            raise ValueError("Người dùng không có tài khoản")

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
                    "balance": format_currency(acc.balance),
                }
            )

        account_ids = [acc.id for acc in accounts]

        # 4. Lấy giao dịch đã hoàn tất
        transactions_query = (
            select(Transaction)
            .where(
                or_(
                    col(Transaction.sender_account_id).in_(account_ids),
                    col(Transaction.receiver_account_id).in_(account_ids),
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
                else "VND"
            )

            transaction_data.append(
                {
                    "reference": txn.reference,
                    "date": txn.created_at.strftime("%Y-%m-%d"),
                    "description": txn.description,
                    "transaction_type": txn.transaction_type.value,
                    "transaction_category": txn.transaction_category.value,
                    "amount": format_currency(txn.amount),
                    "balance_after": format_currency(txn.balance_after),
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
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
        raise
    except Exception as e:
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
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
            "message": "Đang bắt đầu tạo sao kê.",
            "statement_id": statement_id,
            "task_id": task.id,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
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
                detail={"status": "error", "message": "Giao dịch không tìm thấy"},
            )

        transaction, risk_score = transaction_data

        # 2. Chỉ cho phép review giao dịch đang bị FLAGGED
        if transaction.ai_review_status != AIReviewStatusEnum.FLAGGED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Giao dịch không được đánh dấu nghi ngờ gian lận",
                    "current_status": transaction.ai_review_status,
                },
            )

        # 3. Reviewer xác nhận giao dịch có gian lận hay không
        if is_fraud:
            # Reviewer xác nhận là gian lận
            transaction.ai_review_status = AIReviewStatusEnum.CONFIRMED_FRAUD
            transaction.status = TransactionStatusEnum.Failed
            transaction.failed_reason = TransactionFailureReason.SUSPICIOUS_ACTIVITY.value

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
            "message": "Giao dịch đã được đánh giá",
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
        logger.error(f"Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi hệ thống đã xảy ra trong quá trình xử lý yêu cầu",
                "action": "Please try again later",
            },
        )
async def _complete_approved_transfer(
    transaction: Transaction,
    session: AsyncSession,
):
    """
    Hoàn tất giao dịch CHUYỂN TIỀN đã được reviewer chấp thuận
    (áp dụng cho hệ thống VND-only, không FX).
    """
    try:
        # 1. Load entities liên quan
        sender = await session.get(User, transaction.sender_id)
        receiver = await session.get(User, transaction.receiver_id)
        sender_account = await session.get(BankAccount, transaction.sender_account_id)
        receiver_account = await session.get(
            BankAccount, transaction.receiver_account_id
        )

        # 2. Validate dữ liệu bắt buộc
        if not sender:
            raise ValueError("Người gửi không tìm thấy")
        if not receiver:
            raise ValueError("Người nhận không tìm thấy")
        if not sender_account:
            raise ValueError("Tài khoản người gửi không tìm thấy")
        if not receiver_account:
            raise ValueError("Tài khoản người nhận không tìm thấy")

        # 3. Kiểm tra số dư người gửi
        sender_balance = Decimal(str(sender_account.balance))
        if sender_balance < transaction.amount:
            raise ValueError("Số dư không đủ")

        # 4. Cập nhật số dư (atomic logic)
        sender_account.balance = sender_balance - transaction.amount
        receiver_account.balance = (
            Decimal(str(receiver_account.balance)) + transaction.amount
        )

        # 5. Hoàn tất giao dịch
        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        session.add_all([sender_account, receiver_account, transaction])
        await session.commit()

        # 6. Refresh sau commit
        await session.refresh(transaction)
        await session.refresh(sender_account)
        await session.refresh(receiver_account)

        # 7. Gửi email thông báo (best-effort)
        try:
            await send_transfer_alert(
                sender_email=sender.email,
                receiver_email=receiver.email,
                sender_name=sender.full_name,
                receiver_name=receiver.full_name,
                sender_account_number=sender_account.account_number or "Unknown",
                receiver_account_number=receiver_account.account_number or "Unknown",
                amount=transaction.amount,
                description=transaction.description,
                reference=transaction.reference,
                transaction_date=transaction.completed_at,
                sender_balance=sender_account.balance,
                receiver_balance=receiver_account.balance,
            )
            logger.info(
                f"Giao dịch chuyển khoản đã được phê duyệt và hoàn tất với mã tham chiếu {transaction.reference}."
            )
        except Exception as email_error:
            logger.error(
                f"Giao dịch chuyển khoản đã hoàn tất, tuy nhiên quá trình gửi email gặp lỗi: {email_error}."
            )

    except ValueError as e:
        # Lỗi nghiệp vụ → đánh dấu FAILED
        await session.rollback()
        logger.error(f"Phát sinh lỗi nghiệp vụ trong giao dịch chuyển khoản đã được phê duyệt: {e}.")

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
        # Lỗi hệ thống
        await session.rollback()
        logger.error(f"Phát sinh lỗi hệ thống trong quá trình xử lý giao dịch chuyển khoản đã được phê duyệt: {e}.")
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
            raise ValueError("Người dùng không tìm thấy")
        if not account:
            raise ValueError("Tài khoản không tìm thấy")

        # Kiểm tra số dư tài khoản trước khi rút
        if Decimal(str(account.balance)) < transaction.amount:
            raise ValueError("Số dư không đủ")

        try:
            # Trừ tiền khỏi số dư tài khoản
            account.balance = Decimal(str(account.balance)) - transaction.amount

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
                    f"Gửi thông báo rút tiền thành công cho người dùng "
                    f"giao dịch rút tiền {transaction.reference}"
                )
            except Exception as e:
                # Lỗi gửi notification không ảnh hưởng đến giao dịch
                logger.error(
                    f"Không thể gửi thông báo phê duyệt rút tiền: {e}"
                )

        except Exception as e:
            # Lỗi xảy ra trong quá trình xử lý rút tiền
            await session.rollback()
            raise ValueError(f"Xử lý yêu cầu rút tiền thất bại: {str(e)}")

    except ValueError as e:
        # Lỗi nghiệp vụ / validation
        await session.rollback()
        logger.error(
            f"Lỗi xác thực dữ liệu trong quá trình hoàn tất rút tiền đã được phê duyệt: {e}"
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
            f"Lỗi không xác định trong quá trình hoàn tất giao dịch chuyển khoản đã được phê duyệt: {e}"
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
        logger.error(f"Lỗi khi lấy lịch sử rủi ro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Không thể lấy lịch sử rủi ro",
                "action": "Vui lòng thử lại sau",
            },
        )

async def get_all_risk_history_service(
    session: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_risk_score: float | None = None,
    skip: int = 0,
    limit: int = 20,
):
    base_stmt = (
        select(Transaction, TransactionRiskScore)
        .join(TransactionRiskScore)
    )

    if start_date:
        base_stmt = base_stmt.where(
            TransactionRiskScore.created_at >= start_date
        )

    if end_date:
        base_stmt = base_stmt.where(
            TransactionRiskScore.created_at <= end_date
        )

    if min_risk_score is not None:
        base_stmt = base_stmt.where(
            TransactionRiskScore.risk_score >= min_risk_score
        )


    total_stmt = (
        select(func.count())
        .select_from(base_stmt.subquery())
    )
    total = (await session.exec(total_stmt)).one()

    data_stmt = (
        base_stmt
        .order_by(desc(TransactionRiskScore.created_at))
        .offset(skip)
        .limit(limit)
    )

    rows = (await session.exec(data_stmt)).all()

    history: list[dict[str, Any]] = []
    for transaction, risk_score in rows:
        history.append(
            {
                "transaction_id": transaction.id,
                "reference": transaction.reference,
                "amount": str(transaction.amount),
                "created_at": transaction.created_at,
                "risk_score": risk_score.risk_score,
                "risk_factors": risk_score.risk_factors,
                "review_status": transaction.ai_review_status,
                "is_confirmed_fraud": risk_score.is_confirmed_fraud,
                "reviewed_by": risk_score.reviewed_by,
                "review_details": (
                    transaction.transaction_metadata.get("fraud_review")
                    if transaction.transaction_metadata
                    else None
                ),
            }
        )

    return history, total



