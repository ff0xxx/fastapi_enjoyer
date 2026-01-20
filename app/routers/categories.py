from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.db_depends import get_db
from app.schemas import Category as CategorySchema, CategoryCreate
from app.models.categories import Category as CategoryModel


# Создаём маршрутизатор с префиксом и тегом
router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


@router.get("/", response_model=list[CategorySchema])
async def get_all_categories(db: Session = Depends(get_db)):
    """
    Возвращает список всех категорий товаров.
    """
    stmt = select(CategoryModel).where(CategoryModel.is_active == True)
    active_categories = db.scalars(stmt).all()
    return active_categories


@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    """
    Создаёт новую категорию.
    """
    # проверка существования parent_id сучка
    if category.parent_id is not None:
        stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id, 
                                           CategoryModel.is_active == True)
        parent = db.scalars(stmt).first()
        if parent is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent category not found")

    db_category = CategoryModel(**category.model_dump())
    db.add(db_category)
    db.commit()
    # db.refresh(db_category)

    # Тут FastAPI автоматически преобразует объект SQLAlchemy CategoryModel в Pydantic-модель CategorySchema благодаря параметру response_model
    return db_category


@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(category_id: int, new_category: CategoryCreate, db: Session = Depends(get_db)):
    """
    Обновляет категорию по её ID.
    """
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    category = db.scalar(stmt)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Проверка существования parent_id, если указан
    if new_category.parent_id is not None:
        parent_stmt = select(CategoryModel).where(CategoryModel.id == new_category.parent_id,
                                                  CategoryModel.is_active == True)
        parent = db.scalars(parent_stmt).first()
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent category not found")

    db.execute(update(CategoryModel).where(CategoryModel.id == category_id)
               .values(**new_category.model_dump()))
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}")
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    Удаляет категорию по её ID.
    """
    stmt = select(CategoryModel).where(CategoryModel.id == category_id)
    category = db.scalars(stmt).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active=False))
    db.commit()
    return {"status": "success", "message": "Category marked as inactive"}