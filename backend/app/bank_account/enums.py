from enum import Enum


# Enum định nghĩa các loại tài khoản ngân hàng
class AccountTypeEnum(str, Enum):
    Current = "current"          # Tài khoản thanh toán
    Savings = "savings"          # Tài khoản tiết kiệm
    FixedDeposit = "fixed_deposit"  # Tài khoản tiền gửi có kỳ hạn
    Business = "business"        # Tài khoản doanh nghiệp


# Enum định nghĩa trạng thái hoạt động của tài khoản ngân hàng
class AccountStatusEnum(str, Enum):
    Active = "active"            # Tài khoản đang hoạt động
    Inactive = "inactive"        # Tài khoản tạm thời không hoạt động
    Pending = "pending"          # Tài khoản đang chờ xác minh / kích hoạt
    Closed = "closed"            # Tài khoản đã đóng vĩnh viễn
    Frozen = "frozen"            # Tài khoản bị khóa tạm thời


# Enum định nghĩa các loại tiền tệ được hỗ trợ
class AccountCurrencyEnum(str, Enum):
    USD = "USD"                  # Đô la Mỹ
    EUR = "EUR"                  # Euro
    GBP = "GBP"                  # Bảng Anh
    KES = "KES"                  # Đồng Shilling Kenya
    VND = "VND"                  # Đồng Việt Nam