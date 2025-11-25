from sqlalchemy.ext.asyncio import create_async_engine
from database.models import Base
from utils.config import MainConfig

DATABASE_URL = MainConfig.db.DB_CONFIG

engine = create_async_engine(DATABASE_URL, echo=True, future=True)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


