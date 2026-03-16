from enum import Enum


class SalutationEnum(str, Enum):
    # Xưng hô
    Mr = "Mr"
    Mrs = "Mrs"
    Miss = "Miss"


class GenderEnum(str, Enum):
    # Giới tính
    Male = "Male"
    Female = "Female"
    Other = "Other"


class MaritalStatusEnum(str, Enum):
    # Tình trạng hôn nhân
    Married = "Married"# Đã kết hôn
    Divorced = "Divorced"# Đã ly hôn
    Single = "Single"# Độc thân
    Widowed = "Widowed"# Góa phụ


class IdentificationTypeEnum(str, Enum):
    # Nhận dạng các loại giấy tờ
    Passport = "Passport"# Hộ chiếu
    Drivers_License = "Drivers_License"# Giấy phép lái xe
    National_ID = "National_ID"# Chứng minh nhân dân


class EmploymentStatusEnum(str, Enum):
    # Tình trạng việc làm
    Employed = "Employed" # Đang làm việc
    Unemployed = "Unemployed"# Không có việc làm
    Self_Employed = "Self_Employed"# Tự kinh doanh
    Student = "Student"# Sinh viên
    Retired = "Retired"# Đã nghỉ hưu


class ImageTypeEnum(str, Enum):
    # Loại hình ảnh tải lên
    PROFILE_PHOTO = "profile_photo"
    ID_PHOTO = "id_photo"
    SIGNATURE_PHOTO = "signature_photo"