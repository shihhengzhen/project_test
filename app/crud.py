from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Product, Supplier, History
from schemas import ProductCreate, ProductUpdate, SupplierCreate, SupplierUpdate, ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest
from datetime import datetime
from fastapi import HTTPException
from typing import Optional

# 統一錯誤回應格式
def error_response(error_code: str, message: str):
    return {"success": False, "error_code": error_code, "message": message}

# 產品新增
def create_product(db: Session, product: ProductCreate):
    try:
        db_product = Product(**product.model_dump(exclude={"supplier_id"}))
        if product.supplier_id:
            if not isinstance(product.supplier_id, list):
                raise HTTPException(status_code=400, detail=error_response("INVALID_SUPPLIER_ID", "supplier_id必須在列表中"))
            supplier = db.query(Supplier).filter(Supplier.id.in_(product.supplier_id)).all()
            if len(supplier) != len(product.supplier_id):
                raise HTTPException(status_code=400, detail=error_response("INVALID_SUPPLIER_ID", "部分供應商ID錯誤"))
            db_product.supplier = supplier
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 批量新增
def batch_create_product(db: Session, request: BatchCreateRequest):
    created_product = []
    try:
        for product_data in request.product:
            db_product = create_product(db, product_data)
            created_product.append(db_product)
        return created_product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 查詢單一產品
def get_product_by_id(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

# 查詢產品清單
def get_product_list(db: Session, filters: ProductFilter):
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
        product = query.offset(filters.offset).limit(filters.limit).all()
        return {"product": product, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e))) 
       
# 更新產品
def update_product(db: Session, product_id: int, product: ProductUpdate):
    try:
        db_product = get_product_by_id(db, product_id)
        if not db_product:
            return None
        update_data = product.model_dump(exclude_unset=True)
        for field in ["price", "stock"]:
            if field in update_data and getattr(db_product, field) != update_data[field]:
                history_entry = History(
                    product_id=product_id,
                    #name = str(getattr(db_product, name)),
                    field=field,
                    old_value=float(getattr(db_product, field)),
                    new_value=float(update_data[field]),
                )
                db.add(history_entry)
        if "supplier_id" in update_data:
            if update_data["supplier_id"] is not None:
                if not isinstance(update_data["supplier_id"], list):
                    raise HTTPException(status_code=400, detail=error_response("INVALID_SUPPLIER_ID", "supplier_id 必須是整數列表"))
                supplier = db.query(Supplier).filter(Supplier.id.in_(update_data["supplier_id"])).all()
                if len(supplier) != len(update_data["supplier_id"]):
                    raise HTTPException(status_code=400, detail=error_response("INVALID_SUPPLIER_ID", f"無效的供應商 ID: {update_data['supplier_id']}"))
                db_product.supplier = supplier
            else:
                db_product.supplier = []  
            del update_data["supplier_id"]
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
        return db_product
    except HTTPException:
        raise  
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
              
# 批量更新
def batch_update_product(db: Session, request: BatchUpdateRequest):
    updated_products = []
    try:
        for product_data in request.product:
            product_id = getattr(product_data, "id", None)
            if not product_id:
                raise HTTPException(status_code=400, detail=error_response("INVALID_REQUEST", "批量更新請求中缺少產品 ID"))
            updated_product = update_product(db, product_id, product_data)
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
        db_product = get_product_by_id(db, product_id)
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
        deleted_product = []
        for product_id in request.ids:
            product = delete_product(db, product_id)
            if product:
                deleted_product.append(product)
        return deleted_product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

#歷史紀錄
def get_product_history(db: Session, product_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
    try:
        query = db.query(History, Product.name).join(Product, History.product_id == Product.id).filter(History.product_id == product_id)
        if start_date:
            query = query.filter(History.timestamp >= start_date)
        if end_date:
            query = query.filter(History.timestamp <= end_date)
        history = query.order_by(History.timestamp.desc()).all()
        return [
            {
                "product_id": h.product_id,
                "product_name": name,
                "field": h.field,
                "old_value": h.old_value,
                "new_value": h.new_value,
                #"changed_by": h.changed_by,
                "timestamp": h.timestamp
            } for h, name in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
    
# 供應商新增
def create_supplier(db: Session, supplier: SupplierCreate):
    try:
        db_supplier = Supplier(**supplier.model_dump())
        db.add(db_supplier)
        db.commit()
        db.refresh(db_supplier)
        return db_supplier
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))

# 讀取供應商
def get_supplier_by_id(db: Session, supplier_id: int):
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()

# 查詢供應商清單
def get_supplier_list(db: Session, limit: int = 10, offset: int = 0):
    try:
        query = db.query(Supplier)
        total = query.count()
        query = query.offset(offset).limit(limit)
        supplier = query.all()
        return {"supplier": supplier, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))
     
# 更新供應商
def update_supplier(db: Session, supplier_id: int, supplier: SupplierUpdate):
    try:
        db_supplier = get_supplier_by_id(db, supplier_id)
        if not db_supplier:
            return None
        update_data = supplier.model_dump(exclude_unset=True)
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
        db_supplier = get_supplier_by_id(db, supplier_id)
        if db_supplier:
            db.delete(db_supplier)
            db.commit()
        return db_supplier
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=error_response("DATABASE_ERROR", str(e)))