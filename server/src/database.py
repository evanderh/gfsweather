from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
  async_sessionmaker, create_async_engine, AsyncSession
)
from sqlalchemy.ext.declarative import declarative_base

SQLALCHEMY_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@postgis/postgres"
)

engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
session_maker = async_sessionmaker(bind=engine)

Base = declarative_base()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_maker() as session:
        yield session
