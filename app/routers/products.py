from fastapi import APIRouter, status, Depends, HTTPException, Query, File, UploadFile
from sqlalchemy import select, update, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
from pathlib import Path
import uuid

from app.db_depends import get_async_db
from app.schemas import ProductCreate, Product as ProductSchema, ProductList, Review as ReviewSchema
from app.models.categories import Category as CategoryModel
from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.models.reviews import Review as ReviewModel 
from app.auth import get_current_seller


BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media" / "products"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024


async def save_product_image(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPG, PNG or WebP images are allowed")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image is too large")

    extension = Path(file.filename or "").suffix.lower() or ".jpg"
    file_name = f"{uuid.uuid4()}{extension}"
    file_path = MEDIA_ROOT / file_name
    file_path.write_bytes(content)

    return f"/media/products/{file_name}"


async def remove_product_image(url: str | None):
    filename = url.lstrip('/')
    filepath = BASE_DIR / filename
    if filepath.exists():
        filepath.unlink()


# Создаём маршрутизатор для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"],
)


@router.get("/", response_model=ProductList)
async def get_all_products(page: int = Query(1, ge=1),
                           page_size: int = Query(20, ge=1, le=100),
                           category_id: int|None = Query(None),
                           search: str|None = Query(None, min_length=1),
                           min_price: float|None = Query(None, ge=0),
                           max_price: float|None = Query(None, ge=0),
                           in_stock: bool|None = Query(None),
                           seller_id: int|None = Query(None),
                           sort_by_created: bool = Query(False),
                           sort_order: Literal['asc', 'desc'] = Query('asc'), 
                           db: AsyncSession = Depends(get_async_db)):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='min_price must be < max_price')
    
    filters = [ProductModel.is_active==True]
    # Мы против неявных преобразований типов в проде, поэтому is not None!
    if category_id is not None:
        filters.append(ProductModel.category_id == category_id)
    if min_price is not None:
        filters.append(ProductModel.price >= min_price)
    if max_price is not None:
        filters.append(ProductModel.price <= max_price)
    if in_stock is not None:
        filters.append(ProductModel.stock > 0 if in_stock else ProductModel.stock == 0)
    if seller_id is not None:
        filters.append(ProductModel.seller_id == seller_id)

    total_stmt = select(func.count()).select_from(ProductModel).where(*filters)

    rank_col = None
    if search:
        search_value = search.strip()
        if search_value:
            ts_query_en = func.websearch_to_tsquery('english', search_value)
            ts_query_ru = func.websearch_to_tsquery('russian', search_value)
            ts_match_any = or_(
                ProductModel.tsv.op('@@')(ts_query_en),
                ProductModel.tsv.op('@@')(ts_query_ru),
            )
            filters.append(ts_match_any)

            rank_col = func.greatest(
                func.ts_rank_cd(ProductModel.tsv, ts_query_en),
                func.ts_rank_cd(ProductModel.tsv, ts_query_ru),
            ).label("rank")
            total_stmt = select(func.count()).select_from(ProductModel).where(*filters)


    total = await db.scalar(total_stmt) or 0

    order = ProductModel.id
    if sort_by_created:
        order = ProductModel.created_at
    if sort_order == 'desc':
        order = order.desc()

    if rank_col is not None:
        products_stmt = (
            select(ProductModel, rank_col)
            .where(*filters)
            .order_by(desc(rank_col), order)
            .offset((page-1)*page_size)
            .limit(page_size)
        )
        result = await db.execute(products_stmt)
        rows = result.all()
        items = [row[0] for row in rows]
    else:
        products_stmt = (
            select(ProductModel)
            .where(*filters)
            .order_by(order)
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
async def create_product(product: ProductCreate = Depends(ProductCreate.as_form),
                         image: UploadFile | None = File(None),
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Создаёт новый товар.
    """
    category = await db.scalar(select(CategoryModel).where(CategoryModel.id==product.category_id, CategoryModel.is_active==True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Category not found or inactive')

    image_url = await save_product_image(image) if image else None
    db_product = ProductModel(
        **product.model_dump(),
        seller_id=current_user.id,
        image_url=image_url,
    )

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
                         new_product: ProductCreate = Depends(ProductCreate.as_form),
                         image: UploadFile | None = File(None), 
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    """
    Обновляет товар по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    db_product = await db.scalar(stmt)
    if db_product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You can only update your own products')
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    category = await db.scalar(select(CategoryModel).where(CategoryModel.id==new_product.category_id, CategoryModel.is_active == True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Category not found or inactive')

    stmt = update(ProductModel).where(ProductModel.id==product_id).values(**new_product.model_dump())
    await db.execute(stmt)

    if image:
        remove_product_image(db_product.image_url)
        db_product.image_url = await save_product_image(image)

    await db.commit()
    await db.refresh(db_product)  # Для консистентности данных
    return db_product


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
    remove_product_image(product.image_url)
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