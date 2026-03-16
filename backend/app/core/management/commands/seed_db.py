#!/usr/bin/env python
"""
Script khởi tạo dữ liệu mẫu cho cơ sở dữ liệu.
Tạo người dùng, hồ sơ, tài khoản ngân hàng và giao dịch
để cung cấp đủ dữ liệu cho việc kiểm thử các endpoint ML.

PHIÊN BẢN CẢI TIẾN:
- Tăng số lượng users và transactions
- Tỷ lệ fraud thực tế hơn (~3%)
- Risk score cho tất cả transfers (cả fraud và non-fraud)
- Nhiều confirmed fraud hơn để model học tốt hơn
"""

import argparse
import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

# Import models và enums
from backend.app.auth.models import User
from backend.app.auth.schema import (
    AccountStatusSchema,
    SecurityQuestionsSchema
)
from backend.app.role.schema import RoleChoicesSchema
from backend.app.auth.utils import generate_password_hash
from backend.app.bank_account.enums import (
    AccountCurrencyEnum,
    AccountStatusEnum,
    AccountTypeEnum,
)
from backend.app.bank_account.models import BankAccount
from backend.app.bank_account.utils import generate_account_number
from backend.app.core.ai.enums import AIReviewStatusEnum
from backend.app.core.ai.models import TransactionRiskScore
from backend.app.virtual_card.models import VirtualCard
from backend.app.permission.models import Permission
from backend.app.role_permission.models import RolePermission
from backend.app.role.models import Role

# Import database session
from backend.app.core.db import async_session, init_db
from backend.app.next_of_kin.enums import RelationshipTypeEnum
from backend.app.next_of_kin.models import NextOfKin
from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from backend.app.transaction.models import Transaction
from backend.app.user_profile.enums import (
    EmploymentStatusEnum,
    GenderEnum,
    IdentificationTypeEnum,
    MaritalStatusEnum,
    SalutationEnum,
)
from backend.app.user_profile.models import Profile
from backend.app.user_role.models import UserRole

from backend.app.user_profile.schema import CountryShortName, PhoneNumber

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants — đã tăng để ML có đủ dữ liệu
NUM_USERS = 50                  # tăng từ 20 → 50
NUM_TRANSACTIONS_PER_USER = 100 # tăng từ 50 → 100
NUM_FRAUD_TRANSACTIONS = 150    # tăng từ 10 → 150 (~3% tổng)
TRANSACTION_DATE_RANGE = 180    # tăng từ 90 → 180 ngày để dữ liệu phong phú hơn

# Dữ liệu mẫu
FIRST_NAMES = [
    "An", "Anh", "Bảo", "Bình", "Chi", "Dũng", "Dương", "Giang",
    "Hà", "Hải", "Hiếu", "Hương", "Khánh", "Lan", "Linh", "Mai",
    "Minh", "Ngọc", "Quân", "Trang",
]

LAST_NAMES = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ",
    "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý",
    "Đinh", "Trịnh", "Lương", "Châu",
]

CITIES = [
    "Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
    "Nha Trang", "Huế", "Vũng Tàu", "Đà Lạt", "Quy Nhơn",
    "Biên Hòa", "Bình Dương", "Bắc Ninh", "Thanh Hóa", "Nghệ An",
    "Quảng Ninh", "Thái Nguyên", "Nam Định", "Bình Định", "Long An",
]

COUNTRIES = ["VN"]

EMPLOYERS = [
    "Công ty Công nghệ", "Tập đoàn Tài chính", "Bệnh viện Đa khoa",
    "Hệ thống Giáo dục", "Chuỗi Bán lẻ", "Nhà máy Sản xuất",
    "Công ty Năng lượng", "Công ty Xây dựng", "Tập đoàn Du lịch",
    "Công ty Truyền thông",
]

TRANSACTION_DESCRIPTIONS = [
    "Lương chuyển khoản", "Mua sắm siêu thị", "Thanh toán điện nước",
    "Thanh toán tiền thuê nhà", "Mua hàng online", "Phí dịch vụ",
    "Ăn uống nhà hàng", "Chi phí đi lại", "Thanh toán viện phí",
    "Phí bảo hiểm", "Gửi tiết kiệm", "Trả nợ vay", "Học phí",
    "Giải trí", "Chuyển tiền tặng", "Quyên góp từ thiện",
    "Nộp thuế", "Nhận hoàn tiền", "Phí duy trì", "Chi phí bảo trì",
]

# Descriptions thường thấy trong giao dịch fraud
FRAUD_DESCRIPTIONS = [
    "Chuyển tiền khẩn cấp", "Thanh toán đầu tư", "Chuyển vốn kinh doanh",
    "Hỗ trợ tài chính", "Chuyển tiền nước ngoài", "Thanh toán hợp đồng",
]


async def create_users_with_profiles(session: AsyncSession, num_users: int):
    """Tạo người dùng kèm hồ sơ và trả về danh sách"""
    users = []
    admin_user = None
    account_executive_user = None
    teller_user = None

    for i in range(num_users):
        user_id = uuid.uuid4()
        username = f"user{i+1}"
        email = f"user{i+1}@example.com"
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        middle_name = random.choice(FIRST_NAMES) if random.random() > 0.7 else None
        id_no = random.randint(10000000, 99999999)

        if i == 0:
            role = RoleChoicesSchema.SUPER_ADMIN
        elif i == 1:
            role = RoleChoicesSchema.ACCOUNT_EXECUTIVE
        elif i == 2:
            role = RoleChoicesSchema.TELLER
        else:
            role = RoleChoicesSchema.CUSTOMER

        user = User(
            id=user_id,
            username=username,
            email=email,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            id_no=str(id_no),
            hashed_password=generate_password_hash("password123"),
            is_active=True,
            account_status=AccountStatusSchema.ACTIVE,
            security_question=random.choice(list(SecurityQuestionsSchema)),
            security_answer="test answer",
        )

        user_role = UserRole(
            user_id=user_id,
            role_code=role.value,
        )

        if role == RoleChoicesSchema.SUPER_ADMIN:
            admin_user = user
        elif role == RoleChoicesSchema.ACCOUNT_EXECUTIVE:
            account_executive_user = user
        elif role == RoleChoicesSchema.TELLER:
            teller_user = user

        profile = Profile(
            id=uuid.uuid4(),
            user_id=user_id,
            title=random.choice(list(SalutationEnum)),
            gender=random.choice(list(GenderEnum)),
            date_of_birth=datetime.now(timezone.utc)
            - timedelta(days=random.randint(8000, 25000)),
            country_of_birth=CountryShortName(random.choice(COUNTRIES)),
            place_of_birth=random.choice(CITIES),
            marital_status=random.choice(list(MaritalStatusEnum)),
            means_of_identification=random.choice(list(IdentificationTypeEnum)),
            id_issue_date=datetime.now(timezone.utc)
            - timedelta(days=random.randint(100, 1000)),
            id_expiry_date=datetime.now(timezone.utc)
            + timedelta(days=random.randint(100, 1000)),
            passport_number=f"P{random.randint(10000000, 99999999)}",
            nationality=CountryShortName(random.choice(COUNTRIES)),
            phone_number=PhoneNumber(f"+84{random.randint(100000000, 999999999)}"),
            address=f"Số {random.randint(1, 999)} đường {random.choice(['Lê Lợi', 'Trần Hưng Đạo', 'Nguyễn Huệ', 'Hai Bà Trưng', 'Điện Biên Phủ'])}",
            city=random.choice(CITIES),
            country=CountryShortName(random.choice(COUNTRIES)),
            employment_status=random.choice(list(EmploymentStatusEnum)),
            employer_name=random.choice(EMPLOYERS),
            employer_address=f"Số {random.randint(1, 999)} đường {random.choice(['Lê Duẩn', 'Pasteur', 'Lý Thường Kiệt', 'Nguyễn Trãi', 'Cách Mạng Tháng 8'])}",
            employer_city=random.choice(CITIES),
            employer_country=CountryShortName(random.choice(COUNTRIES)),
            annual_income=Decimal(str(random.randint(30000, 150000))),
            date_of_employment=datetime.now(timezone.utc)
            - timedelta(days=random.randint(100, 3000)),
        )

        next_of_kin = NextOfKin(
            id=uuid.uuid4(),
            user_id=user_id,
            full_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            relationship=random.choice(list(RelationshipTypeEnum)),
            email=f"kin{i+1}@example.com",
            phone_number=PhoneNumber(f"+84{random.randint(100000000, 999999999)}"),
            address=f"Số {random.randint(1, 999)} đường {random.choice(['Ngô Quyền', 'Phan Bội Châu', 'Quang Trung', 'Phạm Ngũ Lão', 'Hoàng Diệu'])}",
            city=random.choice(CITIES),
            country=CountryShortName(random.choice(COUNTRIES)),
            nationality=CountryShortName(random.choice(COUNTRIES)),
            is_primary=True,
        )

        session.add(user)
        session.add(profile)
        session.add(next_of_kin)
        session.add(user_role)
        users.append(user)

    await session.commit()

    for user in users:
        await session.refresh(user)

    return users, admin_user, account_executive_user, teller_user


async def ensure_roles(session: AsyncSession):
    """Đảm bảo các role cơ bản tồn tại để thỏa mãn ràng buộc khóa ngoại."""
    role_descriptions = {
        RoleChoicesSchema.CUSTOMER: "Khách hàng",
        RoleChoicesSchema.ACCOUNT_EXECUTIVE: "Nhân viên chăm sóc khách hàng",
        RoleChoicesSchema.BRANCH_MANAGER: "Quản lý chi nhánh",
        RoleChoicesSchema.ADMIN: "Quản trị viên",
        RoleChoicesSchema.SUPER_ADMIN: "Quản trị viên cấp cao",
        RoleChoicesSchema.TELLER: "Giao dịch viên",
    }

    result = await session.exec(select(Role.code))
    existing_codes = set(result.all())

    for role_choice, desc in role_descriptions.items():
        if role_choice.value in existing_codes:
            continue
        session.add(Role(code=role_choice.value, description=desc))

    await session.commit()


async def create_bank_accounts(session: AsyncSession, users):
    """Tạo tài khoản ngân hàng cho người dùng"""
    accounts = []

    for user in users:
        num_accounts = random.randint(1, 2)

        for j in range(num_accounts):
            account_currency = AccountCurrencyEnum.VND
            account_number = generate_account_number(account_currency)

            account = BankAccount(
                id=uuid.uuid4(),
                user_id=user.id,
                account_type=AccountTypeEnum.Savings,
                currency=account_currency,
                account_status=AccountStatusEnum.Active,
                account_number=account_number,
                account_name=f"{user.first_name} {user.last_name}",
                # Tăng số dư ban đầu để đủ tiền cho nhiều giao dịch hơn
                balance=Decimal(str(random.randint(50_000_000, 500_000_000))),
                is_primary=j == 0,
                kyc_submitted=True,
                kyc_verified=True,
                kyc_verified_on=datetime.now(timezone.utc)
                - timedelta(days=random.randint(1, 30)),
            )

            session.add(account)
            accounts.append(account)

    await session.commit()

    for account in accounts:
        await session.refresh(account)

    return accounts


def _build_risk_score(
    transaction: Transaction,
    is_fraud: bool,
    reviewer_id=None,
) -> TransactionRiskScore:
    """
    Tạo bản ghi risk score với các feature phân biệt rõ fraud vs non-fraud.
    Tất cả transfers đều có risk score để model học cả 2 chiều.
    """
    hour = transaction.created_at.hour

    if is_fraud:
        # Đặc điểm fraud: đêm khuya, số tiền lớn, velocity cao
        risk_score_val = random.uniform(0.72, 0.99)
        velocity = random.uniform(0.65, 0.95)
        unusual_hour = hour < 6 or hour > 22  # thường giao dịch đêm khuya
        amount_ratio = random.uniform(0.7, 1.0)  # gần đến giới hạn số dư
    else:
        # Đặc điểm bình thường: ban ngày, số tiền vừa phải, velocity thấp
        risk_score_val = random.uniform(0.01, 0.35)
        velocity = random.uniform(0.05, 0.35)
        unusual_hour = False
        amount_ratio = random.uniform(0.05, 0.4)

    return TransactionRiskScore(
        id=uuid.uuid4(),
        transaction_id=transaction.id,
        risk_score=risk_score_val,
        risk_factors={
            "amount": float(transaction.amount),
            "time_of_day": hour,
            "unusual_hour": unusual_hour,
            "unusual_amount": is_fraud and float(transaction.amount) >= 10_000_000,
            "unusual_pattern": is_fraud,
            "velocity": velocity,
            "amount_to_balance_ratio": amount_ratio,
            "is_round_number": float(transaction.amount) % 1_000_000 == 0,
        },
        ai_model_version="seed_data_v2.0",
        is_confirmed_fraud=is_fraud
        and transaction.ai_review_status == AIReviewStatusEnum.CONFIRMED_FRAUD,
        reviewed_by=reviewer_id,
    )


async def create_transactions(
    session: AsyncSession,
    accounts,
    users,
    date_range_days,
    num_transactions_per_user,
    num_fraud_transactions,
    account_executive=None,
    teller=None,
):
    """Tạo các giao dịch giữa các tài khoản"""
    transactions = []
    all_user_accounts = {}
    account_balances = {acc.id: acc.balance for acc in accounts}

    for account in accounts:
        if account.user_id not in all_user_accounts:
            all_user_accounts[account.user_id] = []
        all_user_accounts[account.user_id].append(account)

    today = datetime.now(timezone.utc)
    start_date = today - timedelta(days=date_range_days)

    # Tạo tất cả giao dịch trước, sau đó sắp xếp theo thời gian
    pending_transactions = []

    for user_id, user_accounts in all_user_accounts.items():
        for _ in range(num_transactions_per_user):
            if not user_accounts:
                continue

            sender_account = random.choice(user_accounts)
            transaction_type = random.choice(list(TransactionTypeEnum))
            transaction_id = uuid.uuid4()
            transaction_reference = f"TRN{uuid.uuid4().hex[:8].upper()}"
            transaction_date = start_date + timedelta(
                days=random.randint(0, date_range_days),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            if random.random() < 0.05:
                amount = Decimal(str(random.randint(10, 100) * 1_000_000))
            elif random.random() < 0.3:
                amount = Decimal(str(random.randint(1, 10) * 1_000_000))
            else:
                amount = Decimal(str(random.randint(1, 50) * 100_000))

            pending_transactions.append({
                "id": transaction_id,
                "reference": transaction_reference,
                "date": transaction_date,
                "amount": amount,
                "description": random.choice(TRANSACTION_DESCRIPTIONS),
                "type": transaction_type,
                "sender_account": sender_account,
                "user_id": user_id,
            })

    pending_transactions.sort(key=lambda x: x["date"])

    for txn_data in pending_transactions:
        transaction_type = txn_data["type"]
        sender_account = txn_data["sender_account"]
        amount = txn_data["amount"]
        user_id = txn_data["user_id"]

        if transaction_type in [
            TransactionTypeEnum.Deposit,
            TransactionTypeEnum.Interest_Credited,
        ]:
            balance_before = account_balances[sender_account.id]
            balance_after = balance_before + amount
            account_balances[sender_account.id] = balance_after

            transaction = Transaction(
                id=txn_data["id"],
                reference=txn_data["reference"],
                amount=amount,
                description=txn_data["description"],
                transaction_type=transaction_type,
                transaction_category=TransactionCategoryEnum.Credit,
                status=TransactionStatusEnum.Completed,
                balance_before=balance_before,
                balance_after=balance_after,
                receiver_account_id=sender_account.id,
                receiver_id=user_id,
                processed_by=teller.id if teller else None,
                created_at=txn_data["date"],
                completed_at=txn_data["date"],
                transaction_metadata={
                    "currency": sender_account.currency.value,
                    "account_number": sender_account.account_number,
                },
                ai_review_status=AIReviewStatusEnum.CLEARED,
            )

        elif transaction_type in [
            TransactionTypeEnum.Withdrawal,
            TransactionTypeEnum.Fee_Charged,
        ]:
            balance_before = account_balances[sender_account.id]
            if balance_before < amount:
                continue # bỏ qua giao dịch nếu không đủ số dư
            balance_after = balance_before - amount
            account_balances[sender_account.id] = balance_after

            transaction = Transaction(
                id=txn_data["id"],
                reference=txn_data["reference"],
                amount=amount,
                description=txn_data["description"],
                transaction_type=transaction_type,
                transaction_category=TransactionCategoryEnum.Debit,
                status=TransactionStatusEnum.Completed,
                balance_before=balance_before,
                balance_after=balance_after,
                sender_account_id=sender_account.id,
                sender_id=user_id,
                processed_by=teller.id if teller else None,
                created_at=txn_data["date"],
                completed_at=txn_data["date"],
                transaction_metadata={
                    "currency": sender_account.currency.value,
                    "account_number": sender_account.account_number,
                },
                ai_review_status=AIReviewStatusEnum.CLEARED,
            )

        else:  # Chuyển khoản
            other_accounts = [acc for acc in accounts if acc.user_id != user_id]
            if not other_accounts:
                continue

            receiver_account = random.choice(other_accounts)
            receiver_id = receiver_account.user_id

            balance_before = account_balances[sender_account.id]
            if balance_before < amount:
                continue

            sender_balance_after = balance_before - amount
            account_balances[sender_account.id] = sender_balance_after
            account_balances[receiver_account.id] += amount

            transaction = Transaction(
                id=txn_data["id"],
                reference=txn_data["reference"],
                amount=amount,
                description=txn_data["description"],
                transaction_type=TransactionTypeEnum.Transfer,
                transaction_category=TransactionCategoryEnum.Debit,
                status=TransactionStatusEnum.Completed,
                balance_before=balance_before,
                balance_after=sender_balance_after,
                sender_account_id=sender_account.id,
                sender_id=user_id,
                receiver_account_id=receiver_account.id,
                receiver_id=receiver_id,
                created_at=txn_data["date"],
                completed_at=txn_data["date"],
                transaction_metadata={
                    "from_currency": sender_account.currency.value,
                    "to_currency": receiver_account.currency.value,
                    "account_number": sender_account.account_number,
                    "counterparty_account": receiver_account.account_number,
                },
                ai_review_status=AIReviewStatusEnum.CLEARED,
            )

        session.add(transaction)
        transactions.append(transaction)

    # Cập nhật số dư cuối vào DB
    for account in accounts:
        account.balance = account_balances[account.id]
        session.add(account)

    await session.commit()


    # GÁN NHÃN FRAUD — cải tiến so với phiên bản cũ
    # Điều kiện lọc fraud_candidates rộng hơn (không giới hạn amount
    # hay 30 ngày) để có đủ candidates để chọn

    all_transfers = [
        t for t in transactions
        if t.transaction_type == TransactionTypeEnum.Transfer
    ]

    logger.info(f"Tổng transfers: {len(all_transfers)}")

    # Chọn các giao dịch fraud
    actual_fraud_count = min(num_fraud_transactions, len(all_transfers))
    fraud_transactions = random.sample(all_transfers, actual_fraud_count)
    fraud_ids = {t.id for t in fraud_transactions}

    # Tỷ lệ confirmed fraud: 60% confirmed, 40% flagged (thay vì chỉ 2 confirmed)
    confirmed_threshold = int(actual_fraud_count * 0.6)
    confirmed_count = 0

    for transaction in fraud_transactions:
        if confirmed_count < confirmed_threshold:
            transaction.ai_review_status = AIReviewStatusEnum.CONFIRMED_FRAUD
            confirmed_count += 1
        else:
            transaction.ai_review_status = AIReviewStatusEnum.FLAGGED

        # Đổi mô tả sang pattern có vẻ gian lận hơn
        transaction.description = random.choice(FRAUD_DESCRIPTIONS)

        # Thêm metadata đánh dấu gian lận
        transaction.transaction_metadata = transaction.transaction_metadata or {}
        transaction.transaction_metadata["fraud_review"] = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "is_fraud": transaction.ai_review_status == AIReviewStatusEnum.CONFIRMED_FRAUD,
            "notes": "Suspicious transfer pattern detected during seeding",
        }

        session.add(transaction)

        # Tạo risk score cho giao dịch fraud
        reviewer = (
            account_executive.id
            if account_executive
            and transaction.ai_review_status == AIReviewStatusEnum.CONFIRMED_FRAUD
            else None
        )
        session.add(_build_risk_score(transaction, is_fraud=True, reviewer_id=reviewer))

    # THÊM MỚI: Risk score cho các giao dịch KHÔNG gian lận
    # Model cần học cả 2 chiều — đây là thứ bản cũ bỏ qua
    non_fraud_transfers = [t for t in all_transfers if t.id not in fraud_ids]

    # Lấy tối đa 3x số fraud để tập non-fraud đủ lớn nhưng không quá chậm
    non_fraud_sample_size = min(len(non_fraud_transfers), actual_fraud_count * 3)
    non_fraud_sample = random.sample(non_fraud_transfers, non_fraud_sample_size)

    for transaction in non_fraud_sample:
        session.add(_build_risk_score(transaction, is_fraud=False))

    await session.commit()

    total_risk_scores = actual_fraud_count + non_fraud_sample_size
    logger.info(
        f"Created {len(transactions)} transactions | "
        f"Fraud: {actual_fraud_count} ({confirmed_count} confirmed, {actual_fraud_count - confirmed_count} flagged) | "
        f"Risk scores: {total_risk_scores} ({actual_fraud_count} fraud + {non_fraud_sample_size} non-fraud)"
    )

    return transactions


async def main(
    num_users, num_transactions_per_user, num_fraud_transactions, transaction_date_range
):
    """Hàm chính để khởi tạo dữ liệu mẫu cho cơ sở dữ liệu"""
    try:
        await init_db()
        logger.info("Database initialized")

        async with async_session() as session:
            await ensure_roles(session)

            logger.info(f"Creating {num_users} users with profiles...")
            users, admin, account_exec, teller = await create_users_with_profiles(
                session, num_users
            )
            logger.info(f"Created {len(users)} users")
            logger.info(f"Admin: {admin.email if admin else 'None'}")
            logger.info(f"Account Executive: {account_exec.email if account_exec else 'None'}")
            logger.info(f"Teller: {teller.email if teller else 'None'}")

            logger.info("Creating bank accounts...")
            accounts = await create_bank_accounts(session, users)
            logger.info(f"Created {len(accounts)} bank accounts")

            logger.info(
                f"Creating ~{num_users * num_transactions_per_user} transactions..."
            )
            transactions = await create_transactions(
                session,
                accounts,
                users,
                transaction_date_range,
                num_transactions_per_user,
                num_fraud_transactions,
                account_executive=account_exec,
                teller=teller,
            )
            logger.info(f"Created {len(transactions)} transactions")
            logger.info("Database seeding completed successfully!")

            logger.info("\nTest Accounts Information:")
            logger.info("--------------------------")
            logger.info(f"Admin: email={admin.email if admin else 'None'}, password=password123")
            logger.info(f"Account Executive: email={account_exec.email if account_exec else 'None'}, password=password123")
            logger.info(f"Teller: email={teller.email if teller else 'None'}, password=password123")

            logger.info("\nSample Customer Accounts:")
            logger.info("--------------------------")
            for i, user in enumerate(users[3:8]):
                logger.info(f"Customer {i+1}: email={user.email}, password=password123")

            logger.info("\nSample Bank Accounts:")
            logger.info("--------------------------")
            for i, account in enumerate(accounts[:5]):
                logger.info(
                    f"Account {i+1}: number={account.account_number}, "
                    f"balance={account.balance:,}, currency={account.currency.value}"
                )

    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Khởi tạo dữ liệu mẫu cho cơ sở dữ liệu")
    parser.add_argument("--users", type=int, default=NUM_USERS)
    parser.add_argument("--transactions", type=int, default=NUM_TRANSACTIONS_PER_USER)
    parser.add_argument("--fraud", type=int, default=NUM_FRAUD_TRANSACTIONS)
    parser.add_argument("--days", type=int, default=TRANSACTION_DATE_RANGE)

    args = parser.parse_args()
    asyncio.run(main(args.users, args.transactions, args.fraud, args.days))