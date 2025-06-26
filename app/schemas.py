from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# 產品
class ProductBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    price: float = Field(..., gt=0, description="價格，必須為正數，最多兩位小數")
    description: Optional[str] = None
    stock: int = Field(..., ge=0, description="庫存，非負整數")
    category: Optional[str] = None
    discount: float = Field(0, ge=0, le=100, description="折扣百分比，範圍 0~100")
    supplier_ids: Optional[List[int]] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    discount: Optional[float] = Field(None, ge=0, le=100)
    supplier_ids: Optional[List[int]] = None
    id: Optional[int] = None  # 為批量更新添加 ID 欄位

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    suppliers: List["SupplierResponse"] = []

    class Config:
        from_attributes = True

class BatchCreateRequest(BaseModel):
    products: List[ProductCreate]

class BatchUpdateRequest(BaseModel):
    products: List[ProductUpdate]

class BatchDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_items=1, description="要刪除的產品 ID 列表")

# 歷史記錄
class HistoryResponse(BaseModel):
    timestamp: datetime
    field: str
    old_value: float
    new_value: float
    changed_by: str

    class Config:
        from_attributes = True

# 供應商
class SupplierBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5, description="評分，範圍 0~5")

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(SupplierBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)

class SupplierResponse(SupplierBase):
    id: int
    products: List[ProductResponse] = []

    class Config:
        from_attributes = True

# 產品過濾
class ProductFilter(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    category: Optional[str] = None
    q: Optional[str] = None
    limit: int = 10
    offset: int = 0
    order_by: Optional[str] = None

# 身份驗證
class LoginRequest(BaseModel):
    username: str
    password: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str