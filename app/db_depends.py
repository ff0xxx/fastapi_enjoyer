from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from collections.abc import Generator


def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

from collections.abc import AsyncGenerator
from app.database import async_session_maker
from sqlalchemy.ext.asyncio import AsyncSession

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
