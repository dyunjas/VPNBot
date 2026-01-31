from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)

from backend.core.config import settings

from backend.database.models import Base

from backend.core.logger_config import logger


engine = create_async_engine(
    settings.POSTGRES_ASYNC_URL,
    poolclass=NullPool,
    echo=False,
    future=True
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