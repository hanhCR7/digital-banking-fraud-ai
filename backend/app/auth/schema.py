from datetime import datetime
from enum import Enum
import uuid
from sqlmodel import SQLModel, Field, Column, String
from pydantic import EmailStr, field_validator
from fastapi import HTTPException, status

class SecurityQuestionsSchema(str, Enum):
    MOTHER_MAIDEN_NAME = "mother_maiden_name"
    CHILDHOOD_FRIEND = "childhood_friend"
    FAVORITE_COLOR = "favorite_color"
    BIRTH_CITY = "birth_city"

@classmethod
def get_description(cls, value: "SecurityQuestionsSchema") -> str:
    descriptions = {
            cls.MOTHER_MAIDEN_NAME: "What is the name of your mother?", # Tên mẹ? 
            cls.CHILDHOOD_FRIEND: "What is the name of your childhood friend?",# tên bạn thời thơ ấu?
            cls.FAVORITE_COLOR: "What is your favorite color?",# Màu yêu thích? 
            cls.BIRTH_CITY: "What is the name of the city you were born in?",# Hỏi nơi sinh?
        }
    return descriptions.get(value, "Unknown security question")

class AccountStatusSchema(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    PENDING = "pending"



class BaseUserSchema(SQLModel):
    username: str | None = Field(default=None, max_length=12, unique=True)
    email: EmailStr = Field(sa_column=Column(String(255), unique=True, index=True))
    first_name: str = Field(max_length=30)
    middle_name: str | None = Field(max_length=30, default=None)
    last_name: str = Field(max_length=30)
    id_no: str = Field(unique=True, min_length=9, max_length=50)# Số giấy tờ tùy thân (CCCD/CMND)
    is_active: bool = False
    is_superuser: bool = False
    security_question: SecurityQuestionsSchema = Field(max_length=30)
    security_answer: str = Field(max_length=30)
    account_status: AccountStatusSchema = Field(default=AccountStatusSchema.INACTIVE)


class UserCreateSchema(BaseUserSchema):
    password: str = Field(min_length=8, max_length=40)
    confirm_password: str = Field(min_length=8, max_length=40)

    @field_validator("confirm_password")
    def validate_confirm_password(cls, v, values):
        if "password" in values.data and v != values.data["password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Passwords do not match",
                    "action": "Please ensure that the passwords you entered match",
                },
            )
        return v
# Schema dùng để trả về thông tin user (không bao gồm password)
class UserReadSchema(BaseUserSchema):
    id: uuid.UUID
    full_name: str
# Schema yêu cầu gửi email (OTP, reset mật khẩu, xác minh)
class EmailRequestSchema(SQLModel):
    email: EmailStr
# Schema đăng nhập bằng email và mật khẩu
class LoginRequestSchema(SQLModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=40
    )
# xác minh mã OTP
class OTPVerifyRequestSchema(SQLModel):
    email: EmailStr
    otp: str = Field(
        min_length=6,
        max_length=6
    )

# Schema thay đổi mật khẩu
class ChangePasswordSchema(SQLModel):
    current_password: str = Field(..., min_length=8, max_length=40)
    new_password: str = Field(..., min_length=8, max_length=40)
    confirm_password: str = Field(..., min_length=8, max_length=40)
    # Xác minh mật khẩu mới và xác nhận mật khẩu có khớp nhau không
    @field_validator("confirm_password")
    def validate_password_match(cls, v, values):
        if "new_password" in values.data and v != values.data["new_password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Xác nhận mật khẩu không hợp lệ.",
                    "action": "Mật khẩu và mật khẩu xác nhận phải giống nhau.",
                },
            )
        return v

class ChangeInitialPasswordSchema(SQLModel):
    user_id: uuid.UUID
    new_password: str = Field(..., min_length=8, max_length=40)
    confirm_password: str = Field(..., min_length=8, max_length=40)
    # Xác minh mật khẩu mới và xác nhận mật khẩu có khớp nhau không
    @field_validator("confirm_password")
    def validate_password_match(cls, v, values):
        if "new_password" in values.data and v != values.data["new_password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Xác nhận mật khẩu không hợp lệ.",
                    "action": "Mật khẩu và mật khẩu xác nhận phải giống nhau.",
                },
            )
        return v
# Schema yêu cầu đặt lại mật khẩu
class PasswordResetRequestSchema(SQLModel):
    email: EmailStr

# Schema xác nhận đặt lại mật khẩu
class PasswordResetConfirmSchema(SQLModel):
    new_password: str = Field(..., min_length=8, max_length=40)
    confirm_password: str = Field(..., min_length=8, max_length=40)
    # Xác minh mật khẩu mới và xác nhận mật khẩu có khớp nhau không
    @field_validator("confirm_password")
    def validate_password_match(cls, v, values):
        if "new_password" in values.data and v != values.data["new_password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Xác nhận mật khẩu không hợp lệ.",
                    "action": "Mật khẩu và mật khẩu xác nhận phải giống nhau."
                },
            )
        return v
class PaginatedUserResponseSchema(SQLModel):
    total: int
    page: int
    size: int
    users: list[UserReadSchema]

class AdminUserCreateSchema(BaseUserSchema):
    is_active: bool = Field(default=True)
    password: str = Field(..., min_length=8, max_length=40)
    confirm_password: str = Field(..., min_length=8, max_length=40)
    @field_validator("confirm_password")
    def validate_passwords_match(cls, v, values):
        if "password" in values.data and v != values.data["password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Passwords do not match",
                    "action": "Please ensure that the passwords you entered match",
                },
            )
        return v  
class AdminUserUpdateSchema(BaseUserSchema):
    password: str | None = Field(default=None, min_length=8, max_length=40)
    confirm_password: str | None = Field(default=None, min_length=8, max_length=40)
    @field_validator("confirm_password")
    def validate_passwords_match(cls, v, values):
        if "password" in values.data and v != values.data["password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Passwords do not match",
                    "action": "Please ensure that the passwords you entered match",
                },
            )
        return v
class AdminUserResponse(SQLModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    first_name: str | None
    middle_name: str | None
    last_name: str | None

    is_active: bool
    account_status: AccountStatusSchema

    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class AdminUserListResponse(SQLModel):
    """Response cho GET /admin/users — danh sách user với key 'Danh sách User'."""

    class Config:
        populate_by_name = True

    danh_sach_user: list[AdminUserResponse] = Field(alias="Danh sách User")