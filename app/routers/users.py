from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db_depends import get_async_db
from app.models.users import User as UserModel
from app.schemas import User as UserSchema, UserCreate
from app.auth import hash_password


router = APIRouter(prefix='/users', tags=['users'])


@router.post('/', response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_async_db)):
    same_user = await db.scalar(select(UserModel).where(UserModel.email==user.email))
    if same_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already registered')
    
    db_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
        role=user.role
    )
    db.add(db_user)
    await db.commit()
    # await db.refresh(db_user)
    return db_user