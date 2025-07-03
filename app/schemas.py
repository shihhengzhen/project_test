from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

# 簡要模型
class ProductShort(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class SupplierShort(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

# 供應商
class SupplierBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5, description="供應商評分，0-5分")
    model_config = {"from_attributes": True}

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(SupplierBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    contact: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)

class SupplierResponse(SupplierBase):
    id: int
    product: Optional[List[ProductShort]] = None

# 產品
class ProductBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    price: float = Field(..., gt=0)
    description: Optional[str] = None
    stock: int = Field(..., ge=0)
    category: Optional[str] = None
    discount: float = Field(0, ge=0, le=100)
    supplier_id: Optional[List[int]] = None
    model_config = {"from_attributes": True}

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
    supplier_id: Optional[List[int]] = None

class ProductUpdate(ProductBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    price: Optional[float] = None
    description: Optional[str] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    discount: Optional[float] = None
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
    supplier_id: Optional[List[int]] = None
    supplier: Optional[List[SupplierShort]] = None
    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj):
        data = super().model_validate(obj).__dict__
        data["supplier_id"] = [s.id for s in obj.supplier] if obj.supplier else []
        return cls(**data)

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
    product_id: int
    product_name: str
    field: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    changed_by: str
    timestamp: datetime
    model_config = {"from_attributes": True}

# 清單回應
class ProductListResponse(BaseModel):
    success: bool = True
    product: List[ProductResponse]
    total: int

class SupplierListResponse(BaseModel):
    success: bool = True
    supplier: List[SupplierResponse]
    total: int