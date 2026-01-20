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
        