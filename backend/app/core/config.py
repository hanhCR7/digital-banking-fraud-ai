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


settings = Setting()