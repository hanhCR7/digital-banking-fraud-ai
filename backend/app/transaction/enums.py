from enum import Enum

# Loại giao dịch
class TransactionTypeEnum(str, Enum):
    Deposit = "deposit"                 # Nạp tiền
    Withdrawal = "withdrawal"           # Rút tiền
    Transfer = "transfer"               # Chuyển tiền
    Reversal = "reversal"               # Hoàn tác giao dịch
    Fee_Charged = "fee_charged"         # Trừ phí
    Loan_Disbursement = "loan_disbursement"  # Giải ngân vay
    Loan_Repayment = "loan_repayment"   # Trả nợ vay
    Interest_Credited = "interest_credited"  # Cộng lãi


# Trạng thái giao dịch
class TransactionStatusEnum(str, Enum):
    Pending = "pending"                 # Đang xử lý
    Completed = "completed"             # Hoàn tất
    Failed = "failed"                   # Thất bại
    Reversed = "reversed"               # Đã hoàn tác
    Cancelled = "cancelled"             # Đã hủy


# Phân loại theo chiều biến động số dư
class TransactionCategoryEnum(str, Enum):
    Credit = "credit"                   # Tăng số dư
    Debit = "debit"                     # Giảm số dư


# Nguyên nhân giao dịch thất bại
class TransactionFailureReason(str, Enum):
    INSUFFICIENT_BALANCE = "insufficient_balance"      # Không đủ số dư
    INVALID_OTP = "invalid_otp"                          # OTP sai
    OTP_EXPIRED = "otp_expired"                          # OTP hết hạn
    CURRENCY_CONVERSION_FAILED = "currency_conversion_failed"  # Lỗi đổi tiền
    ACCOUNT_INACTIVE = "account_inactive"                # Tài khoản không hoạt động
    SYSTEM_ERROR = "system_error"                        # Lỗi hệ thống
    INVALID_AMOUNT = "invalid_amount"                    # Số tiền không hợp lệ
    INVALID_ACCOUNT = "invalid_account"                  # Tài khoản không hợp lệ
    SELF_TRANSFER = "self_transfer"                      # Chuyển cho chính mình
    SUSPICIOUS_ACTIVITY = "suspicious_activity"          # Hoạt động đáng ngờ
