from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings

from backend.database.models import Base

from backend.core.logger_config import logger


engine = create_async_engine(
    settings.POSTGRES_ASYNC_URL,
    pool_size=max(1, int(settings.DB_POOL_SIZE)),
    max_overflow=max(0, int(settings.DB_MAX_OVERFLOW)),
    pool_timeout=max(1, int(settings.DB_POOL_TIMEOUT)),
    pool_recycle=max(60, int(settings.DB_POOL_RECYCLE)),
    pool_use_lifo=True,
    pool_pre_ping=True,
    echo=False,
    future=True,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")

async def check_connection():
    async with async_session() as session:
        try:
            await session.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
        except Exception as e:
            logger.error(F"Database connection failed: {e}")
