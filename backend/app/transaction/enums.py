from enum import Enum


class TransactionTypeEnum(str, Enum):
    Deposit = "deposit"   # Giao dịch nạp tiền vào tài khoản
    Withdrawal = "withdrawal" # Giao dịch rút tiền từ tài khoản
    Transfer = "transfer" # Giao dịch chuyển tiền giữa các tài khoản
    Reversal = "reversal" # Giao dịch hoàn tác (đảo ngược) một giao dịch trước đó
    Fee_Charged = "fee_charged" # Giao dịch trừ phí dịch vụ (phí chuyển tiền, phí duy trì tài khoản...)
    Loan_Disbursement = "loan_disbursement" # Giao dịch giải ngân khoản vay vào tài khoản
    Loan_Repayment = "loan_repayment"  # Giao dịch trả nợ khoản vay (gốc và/hoặc lãi)
    Interest_Credited = "interest_credited" # Giao dịch cộng tiền lãi (tiết kiệm, tiền gửi có kỳ hạn)

class TransactionStatusEnum(str, Enum):
    Pending = "pending"  # Giao dịch đang chờ xử lý (chưa hoàn tất)
    Completed = "completed" # Giao dịch đã được xử lý thành công
    Failed = "failed" # Giao dịch thất bại do lỗi hệ thống hoặc nghiệp vụ
    Reversed = "reversed" # Giao dịch đã hoàn tất nhưng bị hoàn tác (rollback nghiệp vụ)
    Cancelled = "cancelled" # Giao dịch bị hủy trước khi hoàn tất

class TransactionCategoryEnum(str, Enum):
    Credit = "credit" # Giao dịch làm TĂNG số dư tài khoản (nạp tiền, nhận tiền, lãi)
    Debit = "debit" # Giao dịch làm GIẢM số dư tài khoản (rút tiền, chuyển tiền, trả phí)