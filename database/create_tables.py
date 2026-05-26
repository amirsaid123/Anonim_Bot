from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from database.models import Base
from utils.config import MainConfig

DATABASE_URL = MainConfig.db.DB_CONFIG

engine = create_async_engine(DATABASE_URL, echo=True, future=True)


# Idempotent ADD COLUMN statements for fields added after the initial schema.
# Postgres supports IF NOT EXISTS on ADD COLUMN since 9.6, so these are safe
# to re-run on every boot. Long-term, this should move to Alembic.
_POST_CREATE_MIGRATIONS = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS welcome_message TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS locale VARCHAR(8)",
)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _POST_CREATE_MIGRATIONS:
            await conn.execute(text(stmt))
