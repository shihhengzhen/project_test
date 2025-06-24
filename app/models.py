from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# 產品與供應商的多對多關聯表
product_supplier = Table(
    "product_supplier",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id")),
    Column("supplier_id", Integer, ForeignKey("suppliers.id"))
)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False, index=True)
    description = Column(String, nullable=True)
    stock = Column(Integer, nullable=False, default=0)
    category = Column(String, nullable=True, index=True)
    discount = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    suppliers = relationship("Supplier", secondary=product_supplier, back_populates="products")

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    products = relationship("Product", secondary=product_supplier, back_populates="suppliers")