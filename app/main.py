from fastapi import FastAPI, Depends, HTTPException, Query, APIRouter
from sqlalchemy.orm import Session
from database import get_db, Base, engine
from typing import Optional, List
from fastapi.security import OAuth2PasswordRequestForm
from schemas import (
    ProductCreate, ProductResponse, ProductUpdate, SupplierResponse, SupplierCreate, SupplierUpdate,
    ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest, HistoryResponse, ProductListResponse
)
from crud import (
    create_product, get_product_by_id, get_product_list, update_product, delete_product,
    create_supplier, get_supplier_by_id, update_supplier, delete_supplier,
    batch_create_product, batch_update_product, batch_delete_product, get_product_history,
    admin_user, admin_supplier, get_current_user
)
from datetime import datetime
from pydantic import BaseModel
from auth import (
    create_access_token, Token, verify_password, refresh_access_token, create_refresh_token
)
from fastapi.security import OAuth2PasswordBearer
from models import UserRole, User

Base.metadata.create_all(bind=engine)

app = FastAPI()
router = APIRouter()

# 統一錯誤格式
def error_response(error_code: str, message: str):
    return {"success": False, "error_code": error_code, "message": message}

# 定義通用的成功回應模型
class SuccessResponse(BaseModel):
    success: bool = True
    message: str

# 定義批量操作的回應模型
class BatchDeleteResponse(BaseModel):
    success: bool = True
    deleted_count: int

# 定義供應商清單的回應模型
class SupplierListResponse(BaseModel):
    success: bool = True
    supplier: List[SupplierResponse]
    total: int

@app.get("/current_user")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role.value}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail=error_response("INVALID_CREDENTIALS", "Incorrect username or password"))
    access_token = create_access_token(data={"sub": user.username, "role": user.role.value})
    refresh_token = create_refresh_token(data={"sub": user.username, "role": user.role.value})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    return await refresh_access_token(refresh_token, db)


# 產品創建
@app.post("/product/", response_model=ProductResponse)
def create_product_api(product: ProductCreate, db: Session = Depends(get_db)):
    try:
        db_product = create_product(db, product)
        return ProductResponse.model_validate(db_product)
    except HTTPException:
        raise 
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
    
# 批量創建
@app.post("/product/batch_create", response_model=List[ProductResponse])
def batch_create_product_api(request: BatchCreateRequest, db: Session = Depends(get_db)):
    try:
        result = batch_create_product(db, request)
        return [ProductResponse.model_validate(product) for product in result]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
    
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
    try:
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
            product=[ProductResponse.model_validate(product) for product in result["product"]],
            total=result["total"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
    
# 更新產品
@app.put("/product/{id}", response_model=ProductResponse)
def update_product_api(id: int, product: ProductUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_supplier)):
    updated_product = update_product(db, id, product)
    if not updated_product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{id}不存在"))
    if current_user.role == UserRole.supplier:
        supplier_id = [s.id for s in update_product.supplier]
        if not any(sid in product.supplier_id for sid in supplier_id):
            raise HTTPException(status_code=403, detail=error_response("僅管理員或商品的供應商可以做更動"))
    return ProductResponse.model_validate(updated_product)

# 批量更新
@app.put("/product/batch_update", response_model=List[ProductResponse])
def batch_update_product_api(request: BatchUpdateRequest, db: Session = Depends(get_db)):
    try:
        updated_products = batch_update_product(db, request)
        return updated_products  # 直接返回更新後的產品列表
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 刪除產品
@app.delete("/product/{id}", response_model=SuccessResponse)
def delete_product_api(id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_supplier)):
    try:
        if current_user.role == UserRole.supplier:
            supplier_id = [s.id for s in delete_product.supplier]
            if not any(sid in product.supplier_id for sid in supplier_id):
                raise HTTPException(status_code=403, detail=error_response("僅管理員或商品的供應商可以做更動"))
        product = delete_product(db, id)
        if not product:
            raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{id}不存在"))
        return SuccessResponse(message="產品刪除成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 批量刪除
@app.delete("/product/batch_delete", response_model=BatchDeleteResponse)
def batch_delete_product_api(request: BatchDeleteRequest, db: Session = Depends(get_db)):
    try:
        deleted_products = batch_delete_product(db, request)
        return BatchDeleteResponse(deleted_count=len(deleted_products))
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 查詢歷史記錄
@app.get("/product/{id}/history", response_model=List[HistoryResponse])
def get_product_history_api(
    id: int,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_supplier)
):
    try:
        db_product = get_product_by_id(db, id)
        if current_user.role == UserRole.supplier:
            supplier_id = [s.id for s in db_product.supplier]
            if current_user.id not in supplier_id:
                raise HTTPException(status_code=403, detail=error_response("僅管理員或商品的供應商可以做更動"))
        history = get_product_history(db, id, start_date, end_date)
        return history 
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 供應商創建
@app.post("/supplier/", response_model=SupplierResponse)
def create_supplier_api(supplier: SupplierCreate, db: Session = Depends(get_db)):
    try:
        db_supplier = create_supplier(db, supplier)
        return SupplierResponse.model_validate(db_supplier)
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 查詢供應商
@app.get("/supplier/{id}", response_model=SupplierResponse)
def read_supplier(id: int, db: Session = Depends(get_db)):
    supplier = get_supplier_by_id(db, id)
    if not supplier:
        raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{id}不存在"))
    return SupplierResponse.model_validate(supplier)

# 查詢供應商清單
# @app.get("/supplier/", response_model=SupplierListResponse)
# def list_supplier(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
#     try:
#         result = get_supplier_list(db, limit, offset)
#         return SupplierListResponse(supplier=result["supplier"], total=result["total"])
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
    
# 更新供應商
@app.put("/supplier/{id}", response_model=SupplierResponse)
def update_supplier_api(id: int, supplier: SupplierUpdate, db: Session = Depends(get_db)):
    try:
        updated_supplier = update_supplier(db, id, supplier)
        if not updated_supplier:
            raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{id}不存在"))
        return SupplierResponse.model_validate(updated_supplier)
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 刪除供應商
@app.delete("/supplier/{id}", response_model=SuccessResponse)
def delete_supplier_api(id: int, db: Session = Depends(get_db)):
    try:
        supplier = delete_supplier(db, id)
        if not supplier:
            raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{id}不存在"))
        return SuccessResponse(message="供應商刪除成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))