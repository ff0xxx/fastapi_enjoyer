from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_depends import get_async_db
from app.schemas import ProductCreate, Product as ProductSchema, ProductList, Review as ReviewSchema
from app.models.categories import Category as CategoryModel
from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.models.reviews import Review as ReviewModel 
from app.auth import get_current_seller


# Создаём маршрутизатор для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"],
)


@router.get("/", response_model=ProductList)
async def get_all_products(page: int = Query(1, ge=1),
                           page_size: int = Query(20, ge=1, le=100),
                           db: AsyncSession = Depends(get_async_db)):
    total_stmt = select(func.count()).select_from(ProductModel).where(ProductModel.is_active==True)
    total = await db.scalar(total_stmt) or 0

    products_stmt = (
        select(ProductModel)
        .where(ProductModel.is_active==True)
        .order_by(ProductModel.id)
        .offset((page-1)*page_size)
        .limit(page_size)
    )
    items = (await db.scalars(products_stmt)).all()
    products_list = ProductList(items=items, 
                                total=total,
                                page=page, 
                                page_size=page_size)
    return products_list


@router.post("/", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate,
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Создаёт новый товар.
    """
    category = await db.scalar(select(CategoryModel).where(CategoryModel.id==product.category_id, CategoryModel.is_active==True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Category not found or inactive')

    db_product = ProductModel(**product.model_dump(), seller_id = current_user.id)
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)  # в дальнейшем у модели Product будут поля с server_default
    return db_product


@router.get("/category/{category_id}", response_model=list[ProductSchema])
async def get_products_by_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список активных товаров в указанной категории по её ID.
    """
    category = await db.scalar(select(CategoryModel).where(CategoryModel.id==category_id, CategoryModel.is_active==True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found or inactive')

    stmt = select(ProductModel).where(ProductModel.category_id==category_id, ProductModel.is_active==True)
    res = await db.scalars(stmt)
    products = res.all()
    return products


@router.get("/{product_id}", response_model=ProductSchema)
async def get_product(product_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает детальную информацию о товаре по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id==product_id, ProductModel.is_active==True)
    product = await db.scalar(stmt)
    
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found or inactive')
    
    # Проверяем, существует ли активная категория НА САМЫЙ НЕПРЕДВИДЕННЫЙ СЛУЧАЙ
    category = await db.scalar(
        select(CategoryModel).where(CategoryModel.id == product.category_id,
                                    CategoryModel.is_active == True))
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Category not found or inactive")
    return product


@router.put("/{product_id}", response_model=ProductSchema)
async def update_product(product_id: int, 
                         new_product: ProductCreate, 
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Обновляет товар по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    product = await db.scalar(stmt)
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You can only update your own products')
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    category = await db.scalar(select(CategoryModel).where(CategoryModel.id==new_product.category_id, CategoryModel.is_active == True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Category not found or inactive')

    stmt = update(ProductModel).where(ProductModel.id==product_id).values(**new_product.model_dump())
    await db.execute(stmt)
    await db.commit()
    await db.refresh(product)  # Для консистентности данных
    return product


@router.delete("/{product_id}", response_model=ProductSchema)
async def delete_product(product_id: int, 
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Удаляет товар по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    product = await db.scalar(stmt)
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You can only delete your own products')
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found or inactive')
    
    # Проверяем, существует ли активная категория
    category_result = await db.scalars(
        select(CategoryModel).where(CategoryModel.id == product.category_id,
                                    CategoryModel.is_active == True)
    )
    category = category_result.first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    product.is_active = False
    await db.commit()
    await db.refresh(product)  # Для возврата is_active = False
    return product


@router.get('/{product_id}/reviews/', response_model=list[ReviewSchema])
async def get_reviews_by_product_id(product_id: int, db: AsyncSession = Depends(get_async_db)):
    product = await db.scalar(select(ProductModel).where(ProductModel.id==product_id, ProductModel.is_active==True))
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found or inactive')
    result = await db.scalars(select(ReviewModel).where(ReviewModel.product_id==product_id, ReviewModel.is_active==True))
    reviews = result.all()
    return reviews