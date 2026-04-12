from pydantic_settings import BaseSettings

from backend.core.logger_config import logger

class Settings(BaseSettings):
    BOT_TOKEN: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    XRAY_AUTH: str
    PLATEGA_SECRET: str
    PLATEGA_MERCHANT_ID: str
    CRYPTOBOT_SECRET: str
    PALLY_API_TOKEN: str | None = None
    PALLY_SHOP_ID: str | None = None
    PALLY_SUCCESS_URL: str | None = None
    PALLY_FAIL_URL: str | None = None
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_NOREPLY_USER: str
    SMTP_NOREPLY_PASS: str
    OTP_SECRET: str
    PUBLIC_BASE_URL: str
    SECRET_KEY: str
    ADMIN_WEB_TOKEN: str | None = None
    ADMIN_WEB_LOGIN: str | None = None
    ADMIN_WEB_PASSWORD: str | None = None
    ADMIN_WEB_JWT_EXPIRE_HOURS: int = 12
    SUPPORT_FORUM_CHAT_ID: int | None = None
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 0
    DB_POOL_TIMEOUT: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_COMMAND_TIMEOUT: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def POSTGRES_ASYNC_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def POSTGRES_SYNC_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
try:
    settings = Settings()
    logger.info("Settings successfully loaded from .env")
except Exception as e:
    logger.error(f"Error loadding settings from .env")
    raise                                                                                       
                                                                                                  
