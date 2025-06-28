from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
#格式
#簡要
class ProductShort(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True
        
class SupplierShort(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

# 供應商
class SupplierBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5, description="供應商評分，0-5分")
    class Config:
        from_attributes = True

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(SupplierBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5, description="供應商評分，0-5分")

class SupplierResponse(SupplierBase):
    name: str
    contact: Optional[str] = None
    rating: Optional[float] = None
    product: Optional[List[ProductShort]] = None

    model_config = {
        "from_attributes": True,
    }
 
# 產品
class ProductBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    price: float = Field(..., gt=0)
    description: Optional[str] = None
    stock: int = Field(..., ge=0)
    category: Optional[str] = None
    discount: float = Field(0, ge=0, le=100)
    supplier_id: Optional[List[int]] = None

    model_config = {
        "from_attributes": True,
    }

    @field_validator("price")
    def validate_price_precision(cls, value):
        decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(decimal_value)

    @field_validator("discount")
    def validate_discount_precision(cls, value):
        decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(decimal_value)

    @field_validator("supplier_id", mode="before")
    def validate_supplier_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            try:
                value = value.strip("[]").split(",")
                return [int(x.strip()) for x in value if x.strip()]
            except (ValueError, TypeError):
                raise ValueError("supplier_id 必須是整數列表或有效的逗號分隔整數字符串")
        if not isinstance(value, list) or not all(isinstance(x, int) for x in value):
            raise ValueError("supplier_id 必須是整數列表")
        return value
    
class ProductCreate(ProductBase):
    pass
    # name: str
    # price: float
    # description: Optional[str] = None
    # stock: int
    # category: Optional[str] = None
    # discount: float = 0
    supplier_id: Optional[List[int]] = None
    # class Config:
    #     from_attributes = True

class ProductUpdate(ProductBase):
    model_config = {
        "from_attributes": True,  
    }
    #id: Optional[int] = None  
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    price: Optional[float] = Field(None)
    description: Optional[str] = None
    stock: Optional[int] = Field(None)
    category: Optional[str] = None
    discount: Optional[float] = Field(None)
    supplier_id: Optional[List[int]] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float
    description: Optional[str] = None
    stock: int
    category: Optional[str] = None
    discount: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None 
    created_at: datetime
    #supplier_id: Optional[int] = None
    #supplier: Optional[List[SupplierShort]] = None
    model_config = {
        "from_attributes": True,
    }

class BatchCreateRequest(BaseModel):
    product: List[ProductCreate] = Field(..., min_items=1, description="要創建的產品列表")

class BatchUpdateRequest(BaseModel):
    product: List[ProductUpdate] = Field(..., min_items=1, description="要更新的產品列表")

class BatchDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_items=1, description="要刪除的產品ID")
    
# 產品篩選
class ProductFilter(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    category: Optional[str] = None
    q: Optional[str] = None
    name: Optional[str] = None
    limit: int = 10
    offset: int = Field(0, ge=0)
    order_by: Optional[str] = None
    
# 歷史記錄
class HistoryResponse(BaseModel):
    id: int
    product_id: int
    field: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    #changed_by: str
    timestamp: datetime
    
    class Config:
        from_attributes = True

class ProductListResponse(BaseModel):
    product: List[ProductResponse]
    total: int

    model_config = {
        "from_attributes": True,
    }