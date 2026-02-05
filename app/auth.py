from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from datetime import datetime, timezone, timedelta

from app.config import SECRET_KEY, ALGORITHM
from app.db_depends import get_async_db
from app.models.users import User as UserModel


oath2_schema = OAuth2PasswordBearer(tokenUrl='/users/token')
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password.get_secret_value())

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        'exp': expire,
        'token_type': 'access'
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        'exp': expire,
        'token_type': 'refresh'
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oath2_schema), db: AsyncSession = Depends(get_async_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={'WWW-Authenticate': 'Bearer'}
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get('sub')
        if not email:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
        status_code=401,
        detail="Token has expired",
        headers={'WWW-Authenticate': 'Bearer'}
    )
    except jwt.PyJWTError:
        raise credentials_exception

    user = await db.scalar(select(UserModel).where(UserModel.email==email, UserModel.is_active==True))
    if not user:
        raise credentials_exception
    return user


async def get_current_seller(current_user: UserModel = Depends(get_current_user)):
    if current_user.role != 'seller':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only sellers can perform this action")
    return current_user