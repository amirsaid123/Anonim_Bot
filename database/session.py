from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from utils.config import MainConfig

DATABASE_URL = MainConfig.db.DB_CONFIG

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        return session
