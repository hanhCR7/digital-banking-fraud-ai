from datetime import date

from pydantic import field_validator
from pydantic_extra_types.country import CountryShortName
from pydantic_extra_types.phone_numbers import PhoneNumber
from sqlmodel import Field, SQLModel

from backend.app.auth.schema import RoleChoicesSchema
from backend.app.user_profile.enums import (
    EmploymentStatusEnum,
    GenderEnum,
    IdentificationTypeEnum,
    MaritalStatusEnum,
    SalutationEnum,
)
from backend.app.user_profile.utils import validate_id_dates
# Chứa toàn bộ các trường thông tin cá nhân và nghề nghiệp của người dùng
class ProfileBaseSchema(SQLModel):
    title: SalutationEnum 
    gender: GenderEnum
    date_of_birth: date
    country_of_birth: CountryShortName
    place_of_birth: str
    marital_status: MaritalStatusEnum
    means_of_identification: IdentificationTypeEnum
    id_issue_date: date
    id_expiry_date: date
    passport_number: str
    nationality: str
    phone_number: PhoneNumber
    address: str
    city: str
    country: str
    employment_status: EmploymentStatusEnum
    employer_name: str
    employer_address: str
    employer_city: str
    employer_country: CountryShortName
    annual_income: float
    date_of_employment: date
    profile_photo_url: str | None = Field(default=None)
    id_photo_url: str | None = Field(default=None)
    signature_photo_url: str | None = Field(default=None)
