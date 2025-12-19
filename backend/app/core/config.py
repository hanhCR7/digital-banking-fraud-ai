from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal



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
    OTP_EXPIRE_MINUTES: int = 2 if ENVIRONMENT == "local" else 5
    #số lần thử đăng nhập tối đa trước khi bị khóa tài khoản
    LOGIN_ATTEMPTS: int = 3
    # thời gian khóa tài khoản sau khi vượt quá số lần thử đăng nhập.
    LOCKOUT_DURATION_MINUTES: int = 2 if ENVIRONMENT == "local" else 5

settings = Setting()