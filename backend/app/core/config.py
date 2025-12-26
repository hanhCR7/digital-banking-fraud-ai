from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
import cloudinary


class Setting(BaseSettings):
    ENVIRONMENT: Literal["local", "staging", "production"] = "production"
    model_config = SettingsConfigDict(
        env_file="../../.envs/.env.local",
        env_ignore_empty=True,
        extra="ignore"
    )
    API_V1_STR: str = ""
    PROJECT_NAME: str = ""
    PROJECT_DESCRIPTION: str = ""
    SITE_NAME: str = ""
    DATABASE_URL: str = ""
    # mail settings
    MAIL_FROM: str = ""
    MAIL_FROM_NAME: str = ""
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    MAILPIT_UI_PORT: int = 8025

    # Redis settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # RabbitMQ settings
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"

    # User settings
    # thời gian hết hạn của mã OTP
    OTP_EXPIRATION_MINUTES: int = 2 if ENVIRONMENT == "local" else 5
    #số lần thử đăng nhập tối đa trước khi bị khóa tài khoản
    LOGIN_ATTEMPTS: int = 3
    # thời gian khóa tài khoản sau khi vượt quá số lần thử đăng nhập.
    LOCKOUT_DURATION_MINUTES: int = 2 if ENVIRONMENT == "local" else 5
    # thời gian hết hạn của token kích hoạt tài khoản
    ACTIVATION_TOKEN_EXPIRATION_MINUTES: int = 2 if ENVIRONMENT == "local" else 5
    API_BASE_URL: str = ""
    SUPPORT_EMAIL: str = ""
    # JWT settings
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    # Thời gian hết hận access token
    JWT_ACCESS_TOKEN_EXPIRATION_MINUTES: int = 30 if ENVIRONMENT == "local" else 15
    # thời gian hết hạn refresh token
    JWT_REFRESH_TOKEN_EXPIRATION_DAYS: int = 1
    # Cookie settings
    COOKIE_SECURE: bool = False if ENVIRONMENT == "local" else True
    COOKIE_ACCESS_NAME: str = "access_token"
    COOKIE_REFRESH_NAME: str = "refresh_token"
    COOKIE_LOGGED_IN_NAME: str = "logged_in"
    # cấu hình SameSite cho cookie, có thể là 'lax', 'strict' hoặc 'none'
    COOKIE_HTTP_ONLY: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_PATH: str = "/"
    SIGNING_KEY: str = ""
    # THời t=gian hết hạn token đặt lại pass
    PASSWORD_RESET_TOKEN_EXPIRATION_MINUTES: int = 3 if ENVIRONMENT == "local" else 5
    # Cloudinary settings
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    # Cấu hình Cloudinary
    ALLOWED_MIME_TYPES: list[str] = ["image/jpeg", "image/png", "image/jpg"]
    MAX_FILE_SIZE: int = 5 * 1024 * 1024
    MAX_DIMENSION: int = 4096
settings = Setting()
# Cấu hình Cloudinary khi khởi động ứng dụng
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)