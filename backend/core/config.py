from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.logger_config import logger

class Settings(BaseSettings):
    BOT_TOKEN: str
    ERROR_REPORT_BOT_TOKEN: str | None = None
    ERROR_REPORT_CHAT_ID: int = -1003921556376
    ERROR_REPORT_TOPIC_ID: int = 960
    ERROR_REPORT_MAX_BYTES: int = 32_000
    BOT_API_TOKEN: str | None = None
    API_BASE_URL: str | None = None
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    REMNAWAVE_BASE_URL: str | None = None
    REMNAWAVE_API_TOKEN: str | None = None
    REMNAWAVE_COOKIES: str | None = None
    REMNAWAVE_ACTIVE_INTERNAL_SQUADS: str | None = None
    REMNAWAVE_UPSERT_PATH: str | None = None
    REMNAWAVE_AUTO_SYNC_ENABLED: bool = False
    REMNAWAVE_AUTO_SYNC_TIMES: str = "03:00"
    REMNAWAVE_WEBHOOK_EXPIRATION_ENABLED: bool = False
    XRAY_AUTH: str | None = None
    PLATEGA_SECRET: str
    PLATEGA_MERCHANT_ID: str
    CRYPTOBOT_SECRET: str
    PALLY_API_TOKEN: str | None = None
    PALLY_SHOP_ID: str | None = None
    PALLY_SUCCESS_URL: str | None = None
    PALLY_FAIL_URL: str | None = None
    OTP_SECRET: str
    PUBLIC_BASE_URL: str
    SECRET_KEY: str
    ADMIN_API_BASE_URL: str | None = None
    ADMIN_WEB_LOGIN: str | None = None
    ADMIN_WEB_PASSWORD: str | None = None
    ADMIN_WEB_JWT_EXPIRE_HOURS: int = 12
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 0
    DB_POOL_TIMEOUT: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_COMMAND_TIMEOUT: int = 20
    BOT_PROXY: str | None = None
    BOT_PROXY_ENABLED: bool = False
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    API_CORS_ORIGINS: str = (
        "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003,"
        "http://127.0.0.1:8011,http://localhost:8001,http://localhost:8002,"
        "http://localhost:8003,http://localhost:8011"
    )
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_RELOAD: bool = False
    UVICORN_FORWARDED_ALLOW_IPS: str = "127.0.0.1"
    FRONTEND_PROXY_TIMEOUT_SEC: int = 60
    MINIAPP_INITDATA_MAX_AGE_SEC: int = 3600
    TRAFFIC_PRICE_PER_GB_RUB: str = "2"
    MIN_TRAFFIC_PURCHASE_GB: int = 1
    MIN_WITHDRAW_AMOUNT_RUB: int = 500
    MIN_REFERRAL_TRANSFER_AMOUNT_RUB: int = 50
    REFERRAL_BONUS_HOURS: int = 24
    SUBSCRIPTION_RENEWAL_WINDOW_DAYS: int = 3
    CRYPTO_INVOICE_EXPIRES_IN_SEC: int = 900
    PALLY_INVOICE_TTL_SEC: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def POSTGRES_ASYNC_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def POSTGRES_SYNC_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def TELEGRAM_PROXY_URL(self) -> str | None:
        if not self.BOT_PROXY_ENABLED:
            return None
        proxy_url = (self.BOT_PROXY or "").strip()
        return proxy_url or None

    @property
    def API_PROXY_BASE_URL(self) -> str:
        return (self.API_BASE_URL or "http://127.0.0.1:8004").rstrip("/")

    @property
    def API_BASE_URL_JS(self) -> str:
        return (self.API_BASE_URL or "").strip()

    @property
    def ADMIN_API_BASE_URL_JS(self) -> str:
        return (self.ADMIN_API_BASE_URL or self.API_BASE_URL or "http://127.0.0.1:8004").strip()

    @property
    def API_CORS_ORIGINS_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.API_CORS_ORIGINS.split(",") if origin.strip()]

try:
    settings = Settings()
    logger.info("Settings successfully loaded from .env")
except Exception as e:
    logger.error("Error loading settings from .env")
    raise
