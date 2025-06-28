from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
#ALTER TABLE product DROP COLUMN supplier_id;
# 產品供應商多對多
product_supplier = Table(
    "product_supplier",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("product.id"), index=True),
    Column("supplier_id", Integer, ForeignKey("supplier.id"), index=True)
)

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
    history = relationship("History", back_populates="product")
    #supplier_id = Column(Integer, ForeignKey("supplier.id"), nullable=True)
    
class Supplier(Base):
    __tablename__ = "supplier"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    product = relationship("Product", secondary=product_supplier, back_populates="supplier")

class History(Base):
    __tablename__ = "history"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False, index=True)
    field = Column(String(50), nullable=False) 
    old_value = Column(Float, nullable=True)  
    new_value = Column(Float, nullable=True)
    #changed_by = Column(String(100), nullable=False)  
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    product = relationship("Product", back_populates="history")