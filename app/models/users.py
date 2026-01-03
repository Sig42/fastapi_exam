from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .products import Product
    from .reviews import Review
    from .cart_items import CartItem
    from .orders import Order

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String, default="buyer")  # "buyer" or "seller"

    products: Mapped[list["Product"]] = relationship("Product", back_populates="seller")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user")
    cart_items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="user",
                                                        cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user",
                                                 cascade="all, delete-orphan")
