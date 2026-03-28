import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


<<<<<<< Updated upstream
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Format: postgresql+asyncpg://user:password@host:5432/dbname?ssl=require"
    )
=======
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://bath_hack_26_user:GEt6Z2C8x6fUVVYPdfLhCyFEZffMyeRg@dpg-d73ucq7fte5s73b8jaug-a.frankfurt-postgres.render.com/bath_hack_26",
)
>>>>>>> Stashed changes

class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session