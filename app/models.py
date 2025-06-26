from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# 產品供應商多對多關聯表
product_supplier = Table(
    "product_supplier",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id"), index=True),
    Column("supplier_id", Integer, ForeignKey("suppliers.id"), index=True)
)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False, index=True)
    description = Column(String, nullable=True)
    stock = Column(Integer, nullable=False, default=0, index=True)
    category = Column(String, nullable=True, index=True)
    discount = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    suppliers = relationship("Supplier", secondary=product_supplier, back_populates="products")
    history = relationship("ProductHistory", back_populates="product")

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    products = relationship("Product", secondary=product_supplier, back_populates="suppliers")

class ProductHistory(Base):
    __tablename__ = "product_history"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    field = Column(String(50), nullable=False)  # 變動欄位：price 或 stock
    old_value = Column(Float, nullable=False)
    new_value = Column(Float, nullable=False)
    changed_by = Column(String, nullable=False)  # 變動者：admin 或 supplier ID
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    product = relationship("Product", back_populates="history")