from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, Text, Boolean
from datetime import datetime

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grade: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)
    comment_date: Mapped[datetime] = mapped_column(default=datetime.now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), nullable=False)

    user: Mapped['User'] = relationship(back_populates='reviews')
    product: Mapped['Product'] = relationship(back_populates='reviews')