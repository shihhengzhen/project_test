from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db, Base, engine
from schemas import (
    ProductCreate, ProductResponse, ProductUpdate, SupplierResponse, SupplierCreate, SupplierUpdate,
    ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest, HistoryResponse,
    LoginRequest, Token
)
from crud import (
    create_product, get_product, update_product, delete_product, get_products,
    create_supplier, get_supplier, update_supplier, delete_supplier,
    batch_create_product, batch_update_product, batch_delete_product, get_product_history
)
from auth import get_current_user, verify_password, create_access_token, fake_users_db
from typing import List, Optional
from datetime import datetime

Base.metadata.create_all(bind=engine)
app = FastAPI()

# 統一錯誤回應格式
def error_response(error_code: str, message: str):
    return {"success": False, "error_code": error_code, "message": message}

# 統一成功回應格式
def success_response(data: dict):
    return {"success": True, "data": data}

# 登入
@app.post("/auth/login", response_model=Token)
def login(request: LoginRequest):
    user = fake_users_db.get(request.username)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail=error_response("INVALID_CREDENTIALS", "無效的帳號或密碼"))
    access_token = create_access_token({"sub": user["username"], "role": user["role"]})
    return success_response({"access_token": access_token, "token_type": "bearer"})

# 產品創建
@app.post("/products/", response_model=ProductResponse)
def create_product_api(product: ProductCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可創建產品"))
    result = create_product(db, product, current_user["username"])
    return success_response(result)

# 批量創建
@app.post("/products/batch_create", response_model=List[ProductResponse])
def batch_create_product_api(request: BatchCreateRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可批量創建產品"))
    result = batch_create_product(db, request, current_user["username"])
    return success_response({"products": result})

# 查詢單一產品
@app.get("/products/{id}", response_model=ProductResponse)
def read_product(id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    product = get_product(db, id)
    if not product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品 ID {id} 不存在"))
    if current_user["role"] == "supplier" and current_user["username"] not in [s.name for s in product.suppliers]:
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "您無權查看此產品"))
    return success_response(product)

# 查詢產品清單
@app.get("/products/", response_model=dict)
def list_products(
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_stock: Optional[int] = Query(None, ge=0),
    max_stock: Optional[int] = Query(None, ge=0),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: Optional[str] = Query(None, regex="^price|stock|created_at$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
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
    result = get_products(db, filters)
    if current_user["role"] == "supplier":
        result["products"] = [p for p in result["products"] if current_user["username"] in [s.name for s in p.suppliers]]
        result["total"] = len(result["products"])
    return success_response(result)

# 更新產品
@app.put("/products/{id}", response_model=ProductResponse)
def update_product_api(id: int, product: ProductUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_product = get_product(db, id)
    if not db_product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品 ID {id} 不存在"))
    if current_user["role"] == "supplier" and current_user["username"] not in [s.name for s in db_product.suppliers]:
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "您無權編輯此產品"))
    if current_user["role"] not in ["admin", "supplier"]:
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員或供應商可編輯產品"))
    updated_product = update_product(db, id, product, current_user["username"])
    if not updated_product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品 ID {id} 不存在"))
    return success_response(updated_product)

# 批量更新
@app.put("/products/batch_update", response_model=List[ProductResponse])
def batch_update_product_api(request: BatchUpdateRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可批量更新產品"))
    updated_products = batch_update_product(db, request, current_user["username"])
    return success_response({"products": updated_products})

# 刪除產品
@app.delete("/products/{id}")
def delete_product_api(id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可刪除產品"))
    product = delete_product(db, id)
    if not product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品 ID {id} 不存在"))
    return success_response({"message": "產品刪除成功"})

# 批量刪除
@app.delete("/products/batch_delete")
def batch_delete_product_api(request: BatchDeleteRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可批量刪除產品"))
    deleted_products = batch_delete_product(db, request)
    return success_response({"deleted_count": len(deleted_products)})

# 查詢歷史記錄
@app.get("/products/{id}/history", response_model=List[HistoryResponse])
def get_product_history_api(id: int, start_date: Optional[datetime] = Query(None), end_date: Optional[datetime] = Query(None),
                           db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    product = get_product(db, id)
    if not product:
        raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品 ID {id} 不存在"))
    if current_user["role"] == "supplier" and current_user["username"] not in [s.name for s in product.suppliers]:
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "您無權查看此產品的歷史記錄"))
    if current_user["role"] == "user":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "一般用戶無權查看歷史記錄"))
    history = get_product_history(db, id, start_date, end_date)
    return success_response(history)

# 供應商創建
@app.post("/suppliers/", response_model=SupplierResponse)
def create_supplier_api(supplier: SupplierCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可創建供應商"))
    result = create_supplier(db, supplier)
    return success_response(result)

# 查詢供應商
@app.get("/suppliers/{id}", response_model=SupplierResponse)
def read_supplier(id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    supplier = get_supplier(db, id)
    if not supplier:
        raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商 ID {id} 不存在"))
    return success_response(supplier)

# 更新供應商
@app.put("/suppliers/{id}", response_model=SupplierResponse)
def update_supplier_api(id: int, supplier: SupplierUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可更新供應商"))
    updated_supplier = update_supplier(db, id, supplier)
    if not updated_supplier:
        raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商 ID {id} 不存在"))
    return success_response(updated_supplier)

# 刪除供應商
@app.delete("/suppliers/{id}")
def delete_supplier_api(id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail=error_response("FORBIDDEN", "僅管理員可刪除供應商"))
    supplier = delete_supplier(db, id)
    if not supplier:
        raise HTTPException(status_code=404, detail=error_response("SUPPLIER_NOT_FOUND", f"供應商 ID {id} 不存在"))
    return success_response({"message": "供應商刪除成功"})