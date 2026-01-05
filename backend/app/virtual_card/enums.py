from enum import Enum


# Trạng thái của thẻ ảo trong hệ thống
class VirtualCardStatusEnum(str, Enum):
    Active = "active"        # Thẻ đang hoạt động
    Inactive = "inactive"    # Thẻ chưa kích hoạt hoặc tạm ngưng
    Pending = "pending"      # Thẻ đang chờ xử lý / phát hành
    Blocked = "blocked"      # Thẻ bị khóa
    Expired = "expired"      # Thẻ đã hết hạn


# Loại thẻ ảo
class VirtualCardTypeEnum(str, Enum):
    Debit = "debit"          # Thẻ ghi nợ
    Credit = "credit"        # Thẻ tín dụng


# Thương hiệu thẻ
class VirtualCardBrandEnum(str, Enum):
    Visa = "visa"            # Thẻ thuộc mạng lưới Visa


# Loại tiền tệ sử dụng cho thẻ
class VirtualCardCurrencyEnum(str, Enum):
    USD = "USD"              # Đô la Mỹ
    EUR = "EUR"              # Euro
    GBP = "GBP"              # Bảng Anh
    KES = "KES"              # Shilling Kenya
    VND = "VND"              # Việt Nam Đồng


# Lý do thẻ bị khóa
class CardBlockReasonEnum(str, Enum):
    Lost = "lost"                            # Thẻ bị mất
    Stolen = "stolen"                        # Thẻ bị đánh cắp
    Suspicious_Activity = "suspicious_activity"  # Hoạt động đáng ngờ
    Customer_Request = "customer_request"    # Khóa theo yêu cầu khách hàng
