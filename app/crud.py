from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Product, Supplier, ProductHistory
from schemas import ProductCreate, ProductUpdate, SupplierCreate, SupplierUpdate, ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest, HistoryResponse
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException

# 統一錯誤回應格式
def error_response(error_code: str, message: str):
    return {"success": False, "error_code": error_code, "message": message}

# 產品新增
def create_product(db: Session, product: ProductCreate, changed_by: str):
    try:
        db_product = Product(**product.dict(exclude={"supplier_ids"}))
        if product.supplier_ids:
            suppliers = db.query(Supplier).filter(Supplier.id.in_(product.supplier_ids)).all()
            if len(suppliers) != len(product.supplier_ids):
                raise HTTPException(status_code=400, detail=error_response("INVALID_SUPPLIER_IDS", "部分供應商 ID 無效"))
            db_product.suppliers = suppliers
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        # 記錄價格和庫存的初始歷史
        db.add(ProductHistory(product_id=db_product.id, field="price", old_value=0, new_value=product.price, changed_by=changed_by))
        db.add(ProductHistory(product_id=db_product.id, field="stock", old_value=0, new_value=product.stock, changed_by=changed_by))
        db.commit()
        return db_product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 批量新增
def batch_create_product(db: Session, request: BatchCreateRequest, changed_by: str):
    created_products = []
    try:
        for product_data in request.products:
            db_product = create_product(db, product_data, changed_by)
            created_products.append(db_product)
        return created_products
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 讀取單一產品
def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

# 進階查詢與過濾
def get_products(db: Session, filters: ProductFilter):
    try:
        query = db.query(Product)
        if filters.min_price is not None:
            query = query.filter(Product.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.filter(Product.price <= filters.max_price)
        if filters.min_stock is not None:
            query = query.filter(Product.stock >= filters.min_stock)
        if filters.max_stock is not None:
            query = query.filter(Product.stock <= filters.max_stock)
        if filters.category:
            query = query.filter(Product.category == filters.category)
        if filters.q:
            query = query.filter(
                or_(Product.name.ilike(f"%{filters.q}%"), Product.description.ilike(f"%{filters.q}%"))
            )
        if filters.order_by:
            if filters.order_by in ["price", "stock", "created_at"]:
                query = query.order_by(getattr(Product, filters.order_by))
        total = query.count()
        query = query.offset(filters.offset).limit(filters.limit)
        products = query.all()
        return {"products": products, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 更新產品
def update_product(db: Session, product_id: int, product: ProductUpdate, changed_by: str):
    try:
        db_product = get_product(db, product_id)
        if not db_product:
            return None
        update_data = product.dict(exclude_unset=True)
        if "supplier_ids" in update_data:
            suppliers = db.query(Supplier).filter(Supplier.id.in_(update_data["supplier_ids"])).all()
            if len(suppliers) != len(update_data["supplier_ids"]):
                raise HTTPException(status_code=400, detail=error_response("INVALID_SUPPLIER_IDS", "部分供應商 ID 無效"))
            db_product.suppliers = suppliers
            del update_data["supplier_ids"]
        if "price" in update_data and update_data["price"] != db_product.price:
            db.add(ProductHistory(
                product_id=product_id,
                field="price",
                old_value=db_product.price,
                new_value=update_data["price"],
                changed_by=changed_by
            ))
        if "stock" in update_data and update_data["stock"] != db_product.stock:
            db.add(ProductHistory(
                product_id=product_id,
                field="stock",
                old_value=db_product.stock,
                new_value=update_data["stock"],
                changed_by=changed_by
            ))
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
        return db_product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 批量更新
def batch_update_product(db: Session, request: BatchUpdateRequest, changed_by: str):
    updated_products = []
    try:
        for product_data in request.products:
            product_id = getattr(product_data, "id", None)
            if not product_id:
                raise HTTPException(status_code=400, detail=error_response("INVALID_REQUEST", "批量更新請求中缺少產品 ID"))
            updated_product = update_product(db, product_id, product_data, changed_by)
            if updated_product:
                updated_products.append(updated_product)
            else:
                raise HTTPException(status_code=404, detail=error_response("PRODUCT_NOT_FOUND", f"產品 ID {product_id} 不存在"))
        return updated_products
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 刪除產品
def delete_product(db: Session, product_id: int):
    try:
        db_product = get_product(db, product_id)
        if db_product:
            db.delete(db_product)
            db.commit()
        return db_product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 批量刪除
def batch_delete_product(db: Session, request: BatchDeleteRequest):
    try:
        deleted_products = []
        for product_id in request.ids:
            product = delete_product(db, product_id)
            if product:
                deleted_products.append(product)
        return deleted_products
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 查詢歷史記錄
def get_product_history(db: Session, product_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
    try:
        query = db.query(ProductHistory).filter(ProductHistory.product_id == product_id)
        if start_date:
            query = query.filter(ProductHistory.timestamp >= start_date)
        if end_date:
            query = query.filter(ProductHistory.timestamp <= end_date)
        return query.all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 供應商新增
def create_supplier(db: Session, supplier: SupplierCreate):
    try:
        db_supplier = Supplier(**supplier.dict())
        db.add(db_supplier)
        db.commit()
        db.refresh(db_supplier)
        return db_supplier
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 讀取供應商
def get_supplier(db: Session, supplier_id: int):
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()

# 查詢供應商清單
def get_suppliers(db: Session, limit: int = 10, offset: int = 0):
    try:
        query = db.query(Supplier)
        total = query.count()
        query = query.offset(offset).limit(limit)
        suppliers = query.all()
        return {"suppliers": suppliers, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 更新供應商
def update_supplier(db: Session, supplier_id: int, supplier: SupplierUpdate):
    try:
        db_supplier = get_supplier(db, supplier_id)
        if not db_supplier:
            return None
        update_data = supplier.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_supplier, key, value)
        db.commit()
        db.refresh(db_supplier)
        return db_supplier
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 刪除供應商
def delete_supplier(db: Session, supplier_id: int):
    try:
        db_supplier = get_supplier(db, supplier_id)
        if db_supplier:
            db.delete(db_supplier)
            db.commit()
        return db_supplier
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))