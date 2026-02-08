from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import get_current_buyer, get_current_user
from app.db_depends import get_async_db
from app.models.users import User as UserModel
from app.models.products import Product as ProductModel
from app.models.reviews import Review as ReviewModel
from app.schemas import Review as ReviewSchema, ReviewCreate


router = APIRouter(prefix='/reviews', tags=['reviews'])


async def update_product_rating(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    product = await db.get(ProductModel, product_id)
    product.rating = avg_rating
    await db.commit()


@router.get('/', response_model=list[ReviewSchema])
async def get_reviews(db: AsyncSession = Depends(get_async_db)):
    result = await db.scalars(select(ReviewModel).where(ReviewModel.is_active==True))
    reviews = result.all()
    return reviews


@router.post('/', response_model=ReviewSchema)
async def create_review(review: ReviewCreate,
                        db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_user)):
    if current_user.role != 'buyer':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't perform this action")
    review_data = review.model_dump()
    review_data["user_id"] = current_user.id
    db_review = ReviewModel(**review_data)
    product = await db.scalar(select(ProductModel).where(ProductModel.id==db_review.product_id, ProductModel.is_active==True))
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found or inactive')
    review_exists = await db.scalar(select(ReviewModel).where(ReviewModel.user_id==db_review.user_id, 
                                                               ReviewModel.product_id==db_review.product_id, 
                                                               ReviewModel.is_active==True))
    if review_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't leave 2 reviews for 1 product")

    db.add(db_review)
    await db.commit()
    await update_product_rating(db, product.id)    
    await db.refresh(db_review)
    return db_review


@router.delete('/{review_id}')
async def delete_review(review_id: int,
                        db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_user)):

    review = await db.scalar(select(ReviewModel).where(ReviewModel.id==review_id, ReviewModel.is_active==True))
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found or inactive')
    if review.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't perform this action")
    
    review.is_active = False
    await db.commit()
    
    product = await db.scalar(select(ProductModel).where(ProductModel.id==review.product_id, ProductModel.is_active==True))
    if product:
        await update_product_rating(db, product.id)

    return {'message': 'Review has successfully deleted'}
    