from fastapi import APIRouter, status, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from decimal import Decimal

from app.db_depends import get_async_db
from app.auth import get_current_user
from app.models.users import User as UserModel
from app.models.cart_items import CartItem as CartItemModel
from app.models.orders import Order as OrderModel, OrderItem as OrderItemModel
from app.schemas import Order as OrderSchema, OrderList as OrderListSchema


router = APIRouter(prefix='/orders', tags=['orders'])


async def _load_order_with_items(db: AsyncSession, order_id: int) -> OrderModel | None:
    """ загружает заказ с позициями и товарами в одном эффективном запросе """
    result = await db.scalars(
        select(OrderModel)
        .options(
            selectinload(OrderModel.items).selectinload(OrderItemModel.product),
        )
        .where(OrderModel.id == order_id)
    )
    return result.first()


@router.post('/checkout', status_code=status.HTTP_201_CREATED, response_model=OrderSchema)
async def checkout_order(current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    res_cart_items = await db.scalars(select(CartItemModel)
                                      .options(selectinload(CartItemModel.product))
                                      .where(CartItemModel.user_id==current_user.id)
                                      .order_by(CartItemModel.id))
    cart_items = res_cart_items.all()
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cart is empty')
    
    order = OrderModel(user_id=current_user.id)
    total_amount = Decimal("0")

    for cart_item in cart_items:
        product = cart_item.product
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Product {product.id} is unavailable')
        if cart_item.quantity > product.stock:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Not enough stock for {product.name}')
        if product.price is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Product {product.name} has no price set')
        
        total_price = cart_item.quantity * product.price
        total_amount += total_price

        order_item = OrderItemModel(product_id=product.id, quantity=cart_item.quantity, 
                                    unit_price=product.price, total_price=total_price)
        
        order.items.append(order_item)

        product.stock -= cart_item.quantity
        
    order.total_amount = total_amount
    db.add(order)
    await db.execute(delete(CartItemModel).where(CartItemModel.user_id==current_user.id))
    await db.commit()

    created_order = await _load_order_with_items(db, order.id)
    if not created_order:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to load created order')
    return created_order


@router.get("/", response_model=OrderListSchema)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_user),
):
    total = await db.scalar(
        select(func.count(OrderModel.id)).where(OrderModel.user_id == current_user.id)
    )
    result = await db.scalars(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.product))
        .where(OrderModel.user_id == current_user.id)
        .order_by(OrderModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = result.all()

    return OrderListSchema(items=orders, total=total or 0, page=page, page_size=page_size)


@router.get('/{order_id}', response_model=OrderSchema)
async def get_order(order_id: int, current_user: UserModel = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    order = await _load_order_with_items(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Order not found')
    return order
