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
        await conn.execute(
            text(
                "ALTER TABLE vpn_users "
                "ADD COLUMN IF NOT EXISTS traffic_limit_bytes BIGINT NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_subscription_plans "
                "ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_subscription_plans "
                "ADD COLUMN IF NOT EXISTS device_limit INTEGER NOT NULL DEFAULT 3"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_subscriptions "
                "ADD COLUMN IF NOT EXISTS device_limit INTEGER NOT NULL DEFAULT 3"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_subscription_plans "
                "ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_subscription_plans "
                "ADD COLUMN IF NOT EXISTS purchase_limit INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_subscription_plans "
                "ADD COLUMN IF NOT EXISTS is_trial BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE vpn_admins "
                "ADD COLUMN IF NOT EXISTS login VARCHAR(64)"
            )
        )
        await conn.execute(text("UPDATE vpn_admins SET role = 'support' WHERE role = 'manager'"))
        await conn.execute(
            text(
                "ALTER TABLE vpn_admins "
                "ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)"
            )
        )
        await conn.execute(text("ALTER TABLE vpn_admins ADD COLUMN IF NOT EXISTS username VARCHAR(64)"))
        await conn.execute(text("ALTER TABLE vpn_admins ADD COLUMN IF NOT EXISTS email VARCHAR(320)"))
        await conn.execute(text("ALTER TABLE vpn_admins ADD COLUMN IF NOT EXISTS user_id INTEGER"))
        await conn.execute(text("UPDATE vpn_admins a SET username = COALESCE(NULLIF(a.username, ''), NULLIF(a.login, ''), 'admin-' || a.id::text) WHERE a.username IS NULL OR a.username = ''"))
        await conn.execute(text("UPDATE vpn_admins a SET email = COALESCE(NULLIF(a.email, ''), u.email, 'admin-' || a.id::text || '@invalid.local') FROM vpn_users u WHERE a.user_id = u.id AND (a.email IS NULL OR a.email = '')"))
        await conn.execute(text("UPDATE vpn_admins SET email = 'admin-' || id::text || '@invalid.local' WHERE email IS NULL OR email = ''"))
        await conn.execute(text("ALTER TABLE vpn_admins ALTER COLUMN username SET NOT NULL"))
        await conn.execute(text("ALTER TABLE vpn_admins ALTER COLUMN email SET NOT NULL"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_vpn_admins_email ON vpn_admins(email)"))
        await conn.execute(text("DROP INDEX IF EXISTS ix_vpn_admins_username"))
        await conn.execute(text("DO $$ DECLARE c RECORD; BEGIN FOR c IN SELECT constraint_name FROM information_schema.constraint_column_usage WHERE table_name='vpn_admins' AND column_name='user_id' LOOP EXECUTE 'ALTER TABLE vpn_admins DROP CONSTRAINT IF EXISTS ' || quote_ident(c.constraint_name); END LOOP; END $$"))
        await conn.execute(text("ALTER TABLE vpn_admins DROP COLUMN IF EXISTS user_id"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_vpn_admins_login ON vpn_admins(login)"))
        await conn.execute(
            text(
                "UPDATE vpn_subscriptions s "
                "SET device_limit = COALESCE(p.device_limit, 3) "
                "FROM vpn_subscription_plans p "
                "WHERE s.plan_id = p.id AND COALESCE(s.device_limit, 0) <= 0"
            )
        )
        await conn.execute(
            text(
                "UPDATE vpn_subscription_plans "
                "SET display_order = id "
                "WHERE COALESCE(display_order, 0) = 0"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS vpn_user_activities ("
                "id SERIAL PRIMARY KEY, "
                "user_id INTEGER NOT NULL REFERENCES vpn_users(id) ON DELETE CASCADE, "
                "category VARCHAR(32) NOT NULL DEFAULT 'system', "
                "action VARCHAR(64) NOT NULL, "
                "source VARCHAR(32) NOT NULL DEFAULT 'system', "
                "amount INTEGER NULL, "
                "traffic_gb NUMERIC(10,2) NULL, "
                "subscription_id INTEGER NULL REFERENCES vpn_subscriptions(id) ON DELETE SET NULL, "
                "transaction_id_ref INTEGER NULL REFERENCES vpn_transactions(id) ON DELETE SET NULL, "
                "note VARCHAR(512) NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_user_activities_user_id ON vpn_user_activities(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_user_activities_subscription_id ON vpn_user_activities(subscription_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vpn_user_activities_transaction_id_ref ON vpn_user_activities(transaction_id_ref)"))
    logger.info("Database tables initialized")

async def check_connection():
    async with async_session() as session:
        try:
            await session.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
        except Exception as e:
            logger.error(F"Database connection failed: {e}")
