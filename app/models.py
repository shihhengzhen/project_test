from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
#https://docs.sqlalchemy.org/en/20/orm/quickstart.html#declare-models

product_supplier = Table(
    "product_supplier",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("product.id", ondelete="CASCADE"), index=True),
    Column("supplier_id", Integer, ForeignKey("supplier.id", ondelete="CASCADE"), index=True)
)

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user") 
    supplier = relationship("Supplier", back_populates="user", uselist=False)

class Product(Base):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False, index=True)
    description = Column(String, nullable=True)
    stock = Column(Integer, nullable=False, default=0, index=True)
    category = Column(String, nullable=True, index=True)
    discount = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    supplier = relationship("Supplier", secondary=product_supplier, back_populates="product")
    history = relationship("History", back_populates="product", passive_deletes=False, cascade="all, delete-orphan")

class Supplier(Base):
    __tablename__ = "supplier"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, unique=True)
    product = relationship("Product", secondary=product_supplier, back_populates="supplier")
    user = relationship("User", back_populates="supplier", uselist=False)

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False, index=True)
    field = Column(String(50), nullable=False)
    old_value = Column(Float, nullable=True)
    new_value = Column(Float, nullable=True)
    changed_by = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    product = relationship("Product", back_populates="history")