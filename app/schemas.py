from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ProductBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    price: float = Field(..., gt=0)
    description: Optional[str] = None
    stock: int = Field(..., ge=0)
    category: Optional[str] = None
    discount: float = Field(0, ge=0, le=100)
    supplier_ids: List[int] = []

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)
    discount: Optional[float] = Field(None, ge=0, le=100)

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    suppliers: List["SupplierResponse"] = []

    class Config:
        orm_mode = True

class SupplierBase(BaseModel):
    name: str
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)

class SupplierCreate(SupplierBase):
    pass

class SupplierResponse(SupplierBase):
    id: int
    class Config:
        orm_mode = True