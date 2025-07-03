from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Product, Supplier, History, User
from schemas import ProductCreate, ProductUpdate, SupplierCreate, SupplierUpdate, ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest
from datetime import datetime
from fastapi import HTTPException, Depends
from typing import Optional
from auth import get_password_hash, get_current_user
from sqlalchemy.exc import SQLAlchemyError

# 統一錯誤回應格式
def error_response(error_code: str, message: str):
    return {"success": False, "error_code": error_code, "message": message}

# 產品新增
def create_product(db: Session, product: ProductCreate, current_user: User):
    try:
        db_product = Product(**product.model_dump(exclude={"supplier_id"}))
        if product.supplier_id:
            if not isinstance(product.supplier_id, list):
                raise HTTPException(
                    status_code=400,
                    detail=error_response("INVALID_SUPPLIER_ID", "供應商ID必須是整數列表")
                )
            supplier = db.query(Supplier).filter(Supplier.id.in_(product.supplier_id)).all()
            if len(supplier) != len(product.supplier_id):
                raise HTTPException(
                    status_code=400,
                    detail=error_response("INVALID_SUPPLIER_ID", "部分供應商ID無效")
                )
            db_product.supplier = supplier
        elif current_user.role == "supplier":
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if supplier:
                db_product.supplier = [supplier]
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise
    finally:
        pass

# 批量新增
def batch_create_product(db: Session, request: BatchCreateRequest, current_user: User):
    try:
        created_products = []
        for product_data in request.product:
            db_product = create_product(db, product_data, current_user)
            created_products.append(db_product)
        return created_products
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

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
        products = query.offset(filters.offset).limit(filters.limit).all()
        return {"product": products, "total": total}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 更新產品
def update_product(db: Session, product_id: int, product: ProductUpdate, current_user: User):
    try:
        db_product = get_product_by_id(db, product_id)
        if not db_product:
            raise HTTPException(
                status_code=404,
                detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{product_id}不存在")
            )
        if current_user.role == "supplier":
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if not supplier or supplier.id not in [s.id for s in db_product.supplier]:
                raise HTTPException(
                    status_code=403,
                    detail=error_response("PERMISSION_DENIED", "僅管理員或商品的供應商可以做更動")
                )

        update_data = product.model_dump(exclude_unset=True)
        for field in ["price", "stock"]:
            if field in update_data and getattr(db_product, field) != update_data[field]:
                history_entry = History(
                    product_id=product_id,
                    field=field,
                    old_value=float(getattr(db_product, field)),
                    new_value=float(update_data[field]),
                    changed_by=current_user.username
                )
                db.add(history_entry)

        if "supplier_id" in update_data:
            if current_user.role == "supplier":
                del update_data["supplier_id"]
            else:
                if update_data["supplier_id"] is not None:
                    if not isinstance(update_data["supplier_id"], list):
                        raise HTTPException(
                            status_code=400,
                            detail=error_response("INVALID_SUPPLIER_ID", "supplier_id 必須是整數列表")
                        )
                    supplier = db.query(Supplier).filter(Supplier.id.in_(update_data["supplier_id"])).all()
                    if len(supplier) != len(update_data["supplier_id"]):
                        raise HTTPException(
                            status_code=400,
                            detail=error_response("INVALID_SUPPLIER_ID", f"無效的供應商 ID: {update_data['supplier_id']}")
                        )
                    db_product.supplier = supplier
                else:
                    db_product.supplier = []
                del update_data["supplier_id"]
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
        return db_product
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 批量更新
def batch_update_product(db: Session, request: BatchUpdateRequest, current_user: User):
    try:
        updated_products = []
        for product_data in request.product:
            product_id = getattr(product_data, "id", None)
            if not product_id:
                raise HTTPException(
                    status_code=400,
                    detail=error_response("INVALID_REQUEST", "批量更新請求中缺少產品 ID")
                )
            updated_product = update_product(db, product_id, product_data, current_user)
            updated_products.append(updated_product)
        return updated_products
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 刪除產品
def delete_product(db: Session, product_id: int, current_user: User):
    try:
        db_product = get_product_by_id(db, product_id)
        if not db_product:
            raise HTTPException(
                status_code=404,
                detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{product_id}不存在")
            )
        if current_user.role == "supplier":
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if not supplier or supplier.id not in [s.id for s in db_product.supplier]:
                raise HTTPException(
                    status_code=403,
                    detail=error_response("PERMISSION_DENIED", "僅管理員或商品的供應商可以做更動")
                )
        db.delete(db_product)
        db.commit()
        return db_product
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 批量刪除
def batch_delete_product(db: Session, request: BatchDeleteRequest, current_user: User):
    try:
        deleted_products = []
        for product_id in request.ids:
            product = delete_product(db, product_id, current_user)
            if product:
                deleted_products.append(product)
        return deleted_products
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 歷史記錄
def get_product_history(db: Session, product_id: int, start_date: Optional[datetime], end_date: Optional[datetime], current_user: User):
    try:
        db_product = get_product_by_id(db, product_id)
        if not db_product:
            raise HTTPException(
                status_code=404,
                detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{product_id}不存在")
            )
        if current_user.role == "supplier":
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if not supplier or supplier.id not in [s.id for s in db_product.supplier]:
                raise HTTPException(
                    status_code=403,
                    detail=error_response("PERMISSION_DENIED", "僅管理員或商品的供應商可以查看歷史記錄")
                )
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
                "changed_by": h.changed_by,
                "timestamp": h.timestamp
            } for h, name in history
        ]
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 供應商新增
def create_supplier(db: Session, supplier: SupplierCreate):
    try:
        db_supplier = Supplier(**supplier.model_dump())
        db.add(db_supplier)
        db.commit()
        db.refresh(db_supplier)

        username = f"supplier_{db_supplier.id}"
        default_password = "123"
        hashed_password = get_password_hash(default_password)
        db_user = User(
            username=username,
            hashed_password=hashed_password,
            role="supplier"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        db_supplier.user_id = db_user.id
        db.commit()
        db.refresh(db_supplier)
        return db_supplier
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 讀取供應商
def get_supplier_by_id(db: Session, supplier_id: int):
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()

# 查詢供應商清單
def get_supplier_list(db: Session, limit: int = 10, offset: int = 0):
    try:
        query = db.query(Supplier)
        total = query.count()
        suppliers = query.offset(offset).limit(limit).all()
        return {"supplier": suppliers, "total": total}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 更新供應商
def update_supplier(db: Session, supplier_id: int, supplier: SupplierUpdate):
    try:
        db_supplier = get_supplier_by_id(db, supplier_id)
        if not db_supplier:
            raise HTTPException(
                status_code=404,
                detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{supplier_id}不存在")
            )
        update_data = supplier.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_supplier, key, value)
        db.commit()
        db.refresh(db_supplier)
        return db_supplier
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

# 刪除供應商
def delete_supplier(db: Session, supplier_id: int):
    try:
        db_supplier = get_supplier_by_id(db, supplier_id)
        if not db_supplier:
            raise HTTPException(
                status_code=404,
                detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{supplier_id}不存在")
            )
        if db_supplier.user_id:
            db_user = db.query(User).filter(User.id == db_supplier.user_id).first()
            if db_user:
                db.delete(db_user)
        db.delete(db_supplier)
        db.commit()
        return db_supplier
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
    except HTTPException:
        raise

def admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail=error_response("403_FORBIDDEN", "僅管理員可以做更動"))
    return current_user

def admin_supplier(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "supplier"]:
        raise HTTPException(status_code=403, detail=error_response("403_FORBIDDEN", "僅管理員或供應商可以做更動"))
    return current_user