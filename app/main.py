from fastapi import FastAPI, Depends, HTTPException, Query, APIRouter
from sqlalchemy.orm import Session
from database import get_db, Base, engine
from typing import Optional, List
from fastapi.security import OAuth2PasswordRequestForm
from schemas import (
    ProductCreate, ProductResponse, ProductUpdate, SupplierResponse, SupplierCreate, SupplierUpdate,
    ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest, HistoryResponse, ProductListResponse, SupplierListResponse
)
from crud import (
    create_product, get_product_by_id, get_product_list, update_product, delete_product,
    create_supplier, get_supplier_by_id, get_supplier_list, update_supplier, delete_supplier,
    batch_create_product, batch_update_product, batch_delete_product, get_product_history,
    admin_user, admin_supplier, get_current_user
)
from datetime import datetime
from pydantic import BaseModel
from auth import create_access_token, Token, verify_password, refresh_access_token, create_refresh_token
from models import User

Base.metadata.create_all(bind=engine)

app = FastAPI()
router = APIRouter()

# 統一錯誤格式
def error_response(error_code: str, message: str):
    return {"success": False, "error_code": error_code, "message": message}

# 成功回應
class SuccessResponse(BaseModel):
    success: bool = True
    message: str

# 批量操作成功
class BatchDeleteResponse(BaseModel):
    success: bool = True
    deleted_count: int

@app.get("/current_user")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {"success": True, "data": {"username": current_user.username, "role": current_user.role}}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail=error_response("INVALID_CREDENTIALS", "帳號或密碼錯誤"))
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    return await refresh_access_token(refresh_token, db)

# 產品創建
@app.post("/product/", response_model=SuccessResponse)
def create_product_api(product: ProductCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_supplier)):
    create_product(db, product, current_user)
    return SuccessResponse(message="產品創建成功")

# 批量創建
@app.post("/product/batch_create", response_model=SuccessResponse)
def batch_create_product_api(request: BatchCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(admin_supplier)):
    batch_create_product(db, request, current_user)
    return SuccessResponse(message="批量產品創建成功")

# 查詢單一產品
@app.get("/product/{id}", response_model=ProductResponse)
def read_product(id: int, db: Session = Depends(get_db)):
    product = get_product_by_id(db, id)
    if not product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{id}不存在"))
    return ProductResponse.model_validate(product)

# 查詢產品清單
@app.get("/product/", response_model=ProductListResponse)
def list_product(
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_stock: Optional[int] = Query(None),
    max_stock: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: Optional[str] = Query(None, pattern="^price|stock|created_at$"),
    db: Session = Depends(get_db),
):
    filters = ProductFilter(
        min_price=min_price,
        max_price=max_price,
        min_stock=min_stock,
        max_stock=max_stock,
        category=category,
        q=q,
        limit=limit,
        offset=offset,
        order_by=order_by
    )
    result = get_product_list(db, filters)
    return ProductListResponse(
        success=True,
        product=[ProductResponse.model_validate(product) for product in result["product"]],
        total=result["total"]
    )

# 更新產品
@app.put("/product/{id}", response_model=SuccessResponse)
def update_product_api(
    id: int,
    product: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_supplier),
):
    update_product(db, id, product, current_user)
    return SuccessResponse(message="產品更新成功")

# 批量更新
@app.put("/product/batch_update", response_model=SuccessResponse)
def batch_update_product_api(request: BatchUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(admin_user)):
    batch_update_product(db, request, current_user)
    return SuccessResponse(message="批量產品更新成功")

# 刪除產品
@app.delete("/product/{id}", response_model=SuccessResponse)
def delete_product_api(id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_supplier)):
    delete_product(db, id, current_user)
    return SuccessResponse(message="產品刪除成功")

# 批量刪除
@app.delete("/product/batch_delete", response_model=BatchDeleteResponse)
def batch_delete_product_api(request: BatchDeleteRequest, db: Session = Depends(get_db), current_user: User = Depends(admin_supplier)):
    deleted_count = len(batch_delete_product(db, request, current_user))
    return BatchDeleteResponse(deleted_count=deleted_count)

# 查詢歷史記錄
@app.get("/product/{id}/history", response_model=List[HistoryResponse])
def get_product_history_api(
    id: int,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_supplier)
):
    history = get_product_history(db, id, start_date, end_date, current_user)
    return history

# 供應商創建
@app.post("/supplier/", response_model=SuccessResponse)
def create_supplier_api(supplier: SupplierCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_user)):
    create_supplier(db, supplier)
    return SuccessResponse(message="供應商創建成功")

# 查詢供應商
@app.get("/supplier/{id}", response_model=SupplierResponse)
def read_supplier(id: int, db: Session = Depends(get_db)):
    supplier = get_supplier_by_id(db, id)
    if not supplier:
        raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{id}不存在"))
    return SupplierResponse.model_validate(supplier)

# 查詢供應商清單
@app.get("/supplier/", response_model=SupplierListResponse)
def list_supplier(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    result = get_supplier_list(db, limit, offset)
    return SupplierListResponse(
        success=True,
        supplier=[SupplierResponse.model_validate(supplier) for supplier in result["supplier"]],
        total=result["total"]
    )

# 更新供應商
@app.put("/supplier/{id}", response_model=SuccessResponse)
def update_supplier_api(id: int, supplier: SupplierUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_user)):
    update_supplier(db, id, supplier)
    return SuccessResponse(message="供應商更新成功")

# 刪除供應商
@app.delete("/supplier/{id}", response_model=SuccessResponse)
def delete_supplier_api(id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_user)):
    delete_supplier(db, id)
    return SuccessResponse(message="供應商刪除成功")