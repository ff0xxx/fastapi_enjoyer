from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db_depends import get_db
from app.schemas import ProductCreate, Product as ProductSchema
from app.models.categories import Category as CategoryModel
from app.models.products import Product as ProductModel


# Создаём маршрутизатор для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"],
)


@router.get("/", response_model=list[ProductSchema])
async def get_all_products(db: Session = Depends(get_db)):
    """
    Возвращает список всех товаров.
    """
    stmt = select(ProductModel).where(ProductModel.is_active==True)
    products = db.scalars(stmt).all()
    return products


@router.post("/", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """
    Создаёт новый товар.
    """
    category = db.scalar(select(CategoryModel).where(CategoryModel.id==product.category_id, CategoryModel.is_active==True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Category not found or inactive')

    db_product = ProductModel(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@router.get("/category/{category_id}", response_model=list[ProductSchema])
async def get_products_by_category(category_id: int, db: Session = Depends(get_db)):
    """
    Возвращает список активных товаров в указанной категории по её ID.
    """
    category = db.scalar(select(CategoryModel).where(CategoryModel.id==category_id, CategoryModel.is_active==True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category id not found or inactive')

    stmt = select(ProductModel).where(ProductModel.category_id==category_id, ProductModel.is_active==True)
    products = db.scalars(stmt).all()
    return products


@router.get("/{product_id}", response_model=ProductSchema)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """
    Возвращает детальную информацию о товаре по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id==product_id, ProductModel.is_active==True)
    product = db.scalar(stmt)
    
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found or inactive')
    
    # Проверяем, существует ли активная категория НА САМЫЙ НЕПРЕДВИДЕННЫЙ СЛУЧАЙ
    category = db.scalar(
        select(CategoryModel).where(CategoryModel.id == product.category_id,
                                    CategoryModel.is_active == True))
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Category not found or inactive")
    return product


@router.put("/{product_id}")
async def update_product(product_id: int, new_product: ProductCreate, db: Session = Depends(get_db)):
    """
    Обновляет товар по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    product = db.scalar(stmt)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    category = db.scalar(select(CategoryModel).where(CategoryModel.id==new_product.category_id, CategoryModel.is_active == True))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Category not found or inactive')

    stmt = update(ProductModel).where(ProductModel.id==product_id).values(**new_product.model_dump())
    db.execute(stmt)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """
    Удаляет товар по его ID.
    """
    stmt = select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    product = db.scalar(stmt)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found or inactive')
    product.is_active = False
    db.commit()
    return {"status": "success", "message": "Product marked as inactive"}
