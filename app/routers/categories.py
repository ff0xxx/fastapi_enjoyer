from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db_depends import get_db, get_async_db
from app.schemas import Category as CategorySchema, CategoryCreate
from app.models.categories import Category as CategoryModel


# Создаём маршрутизатор с префиксом и тегом
router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


@router.get("/", response_model=list[CategorySchema])
async def get_all_categories(db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список всех категорий товаров.
    """
    result = await db.scalars(select(CategoryModel).where(CategoryModel.is_active==True))
    categories = result.all()
    return categories

# TODO: защитить не-гет эндпоинты с get_current_seller
@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_async_db)):
    """
    Создаёт новую категорию.
    """
    # проверка существования parent_id сучка
    if category.parent_id is not None:
        stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id, 
                                           CategoryModel.is_active == True)
        res = await db.scalars(stmt)
        parent = res.first()
        if parent is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent category not found")

    db_category = CategoryModel(**category.model_dump())
    db.add(db_category)
    await db.commit()
    # await db.refresh(db_category)

    # Тут FastAPI автоматически преобразует объект SQLAlchemy CategoryModel в Pydantic-модель CategorySchema благодаря параметру response_model
    return db_category


@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(category_id: int, new_category: CategoryCreate, db: AsyncSession = Depends(get_async_db)):
    """
    Обновляет категорию по её ID.
    """
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    res = await db.scalars(stmt)
    category = res.first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Проверка существования parent_id, если указан
    if new_category.parent_id is not None:
        parent_stmt = select(CategoryModel).where(CategoryModel.id == new_category.parent_id,
                                                  CategoryModel.is_active == True)
        res = await db.scalars(parent_stmt)
        parent = res.first()
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent category not found")
        if parent.id == category_id:
            raise HTTPException(status_code=400, detail="Category can't be its own parent")
            
    update_data = new_category.model_dump(exclude_unset=True)
    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id)
                     .values(**update_data))
    await db.commit()
    # db.refresh(category)  # нет необходимости, тк expire_on_commit=False
    return category


@router.delete("/{category_id}", response_model=CategorySchema)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Удаляет категорию по её ID.
    """
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    res = await db.scalars(stmt)
    category = res.first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active=False))
    await db.commit()
    return category
