from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Product, Supplier, History, User, product_supplier
from schemas import ProductCreate, ProductUpdate, SupplierCreate, SupplierUpdate, ProductFilter, BatchCreateRequest, BatchUpdateRequest, BatchDeleteRequest, SuccessResponse, HistoryResponse
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
        # 創建產品物件，排除supplier_id
        db_product = Product(**product.model_dump(exclude={"supplier_id"}))
        # 處理供應商關聯
        if product.supplier_id:
            # 驗證supplier_id是整數列表
            if not isinstance(product.supplier_id, list) or not all(isinstance(id, int) for id in product.supplier_id):
                raise HTTPException(
                    status_code=400,
                    detail=error_response("INVALID_SUPPLIER_ID", "供應商ID必須是整數列表")
                )
            # 查詢供應商
            supplier = db.query(Supplier).filter(Supplier.id.in_(product.supplier_id)).all()
            if len(supplier) != len(product.supplier_id):
                raise HTTPException(
                    status_code=400,
                    detail=error_response("INVALID_SUPPLIER_ID", "部分供應商ID無效")
                )
            db_product.supplier = supplier
        elif current_user.role == "supplier":
            # 供應商自動連到自己的供應商記錄
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if supplier:
                db_product.supplier = [supplier]
        db.add(db_product)
        db.commit()
        return SuccessResponse(message="產品創建成功")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 批量新增
def batch_create_product(db: Session, request: BatchCreateRequest, current_user: User):
    try:
        # 檢查產品列表是否為空
        if not request.product:
            raise HTTPException(
                status_code=400,
                detail=error_response("EMPTY_PRODUCT_LIST", "產品列表不能為空")
            )
        product_ids = []
        with db.begin():  # 若中途失敗，可能導致部分產品創建成功
            for product_data in request.product:
                result = create_product(db, product_data, current_user)
                product_ids.extend(result.product_ids or [])
        return SuccessResponse(message="批量產品創建成功")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 查詢單一產品
def get_product_by_id(db: Session, product_id: int):
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=404,
                detail=error_response("PRODUCT_NOT_FOUND", f"產品ID:{product_id}不存在")
            )
        return product
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
# 查詢產品清單
def get_product_list(db: Session, filters: ProductFilter):
    try:
        # 驗證篩選條件
        if filters.min_price is not None and filters.max_price is not None and filters.min_price > filters.max_price:
            raise HTTPException(
                status_code=400,
                detail=error_response("INVALID_PRICE_RANGE", "最低價格不能大於最高價格")
            )
        if filters.min_stock is not None and filters.max_stock is not None and filters.min_stock > filters.max_stock:
            raise HTTPException(
                status_code=400,
                detail=error_response("INVALID_STOCK_RANGE", "最低庫存不能大於最高庫存")
            )
        # 查詢
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
        # 計算總記錄數
        total = query.count()
        products = query.offset(filters.offset).limit(filters.limit).all()
        # 檢查空結果
        if not products and total == 0:
            raise HTTPException(
                status_code=404,
                detail=error_response("NO_PRODUCTS_FOUND", "無符合條件的產品")
            )
        return {"product": products, "total": total}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 更新產品
def update_product(db: Session, product_id: int, product: ProductUpdate, current_user: User):
    try:
        # 檢查產品是否存在
        db_product = get_product_by_id(db, product_id)
        # 權限檢查，供應商只能更新自己的產品
        if current_user.role == "supplier":
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if not supplier or supplier.id not in [s.id for s in db_product.supplier]:
                raise HTTPException(
                    status_code=403,
                    detail=error_response("PERMISSION_DENIED", "僅管理員或商品的供應商可以做更動")
                )
        # 獲取更新資料
        update_data = product.model_dump(exclude_unset=True)
        # 記錄價格和庫存變更後放入資料庫
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
        # 處理供應商部分
        if "supplier_id" in update_data:
            # 供應商無法修改供應商
            if current_user.role == "supplier":
                del update_data["supplier_id"]
            else:
                # 驗證supplier_id是否為整數
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
                    db_product.supplier = []# 清空供應商
                del update_data["supplier_id"]
        # 更新產品欄位
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        return SuccessResponse(message="產品更新成功")#, product_id=product_id
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 批量更新
def batch_update_product(db: Session, request: BatchUpdateRequest, current_user: User):
    try:
        # 檢查產品列表是否為空
        if not request.product:
            raise HTTPException(
                status_code=400,
                detail=error_response("EMPTY_PRODUCT_LIST", "產品列表不能為空")
            )        
        with db.begin(): # 若中途失敗，可能導致部分產品創建成功
            for product_data in request.product:
                product_id = getattr(product_data, "id", None)
                update_product(db, product_id, product_data, current_user)
        return SuccessResponse(message="批量產品更新成功")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 刪除產品
def delete_product(db: Session, product_id: int, current_user: User):
    try:
        # 檢查產品是否存在
        db_product = get_product_by_id(db, product_id)
        # 權限檢查，供應商只能刪除自己的產品
        if current_user.role == "supplier":
            supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
            if not supplier or supplier.id not in [s.id for s in db_product.supplier]:
                raise HTTPException(
                    status_code=403,
                    detail=error_response("PERMISSION_DENIED", "僅管理員或商品的供應商可以做更動")
                )
        # 執行刪除
        db.delete(db_product)
        db.commit()
        return SuccessResponse(message="產品刪除成功")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 批量刪除
def batch_delete_product(db: Session, request: BatchDeleteRequest, current_user: User):
    try:
        # 檢查ID列表是否為空
        if not request.ids:
            raise HTTPException(
                status_code=400,
                detail=error_response("EMPTY_PRODUCT_LIST", "產品ID列表不能為空")
            )
        with db.begin():
            for product_id in request.ids:
                delete_product(db, product_id, current_user)
        return SuccessResponse(message="批量產品刪除成功")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 歷史記錄
def get_product_history(db: Session, product_id: int, start_date: Optional[datetime], end_date: Optional[datetime], current_user: User):
    try:
        # 檢查產品是否存在
        db_product = get_product_by_id(db, product_id)
        # 權限檢查，供應商只能查看自己的產品
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
        # 檢查空結果!!!!
        # if not history:
        #     return SuccessResponse(message="無更改紀錄")
        return [
            {
                "product_id": history.product_id,
                "product_name": name,
                "field": history.field,
                "old_value": history.old_value,
                "new_value": history.new_value,
                "changed_by": history.changed_by,
                "timestamp": history.timestamp
            } for history, name in history
        ]
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

# 供應商新增
def create_supplier(db: Session, supplier: SupplierCreate):
    try:
        with db.begin():  
            # 創建供應商
            db_supplier = Supplier(**supplier.model_dump())
            db.add(db_supplier)
            # 創建關聯用戶
            username = f"supplier_{db_supplier.id}"
            default_password = "123"
            hashed_password = get_password_hash(default_password)
            db_user = User(
                username=username,
                hashed_password=hashed_password,
                role="supplier"
            )
            db.add(db_user)

            # 關聯用戶
            db_supplier.user_id = db_user.id
            db.commit()
        
        return SuccessResponse(message="供應商創建成功") 
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
        
# 讀取供應商
def get_supplier_by_id(db: Session, supplier_id: int):
    if not isinstance(supplier_id, int) or supplier_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=error_response("INVALID_SUPPLIER_ID", "供應商ID必須為正整數")
        )
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()

# 查詢供應商清單
def get_supplier_list(db: Session, limit: int = 10, offset: int = 0):
    try:
        if limit <= 0 or offset < 0:
            raise HTTPException(
                status_code=400,
                detail=error_response("INVALID_PAGINATION", "limit必須為正整數，offset必須為非負整數")
            )
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
        return SuccessResponse(message="供應商更新成功")
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )
        
# 刪除供應商
def delete_supplier(db: Session, supplier_id: int):
    try:
        db_supplier = get_supplier_by_id(db, supplier_id)
        if not db_supplier:
            raise HTTPException(
                status_code=404,
                detail=error_response("SUPPLIER_NOT_FOUND", f"供應商ID:{supplier_id}不存在")
            )
        with db.begin():
            # 刪除供應商的所有產品
            db.query(Product).join(product_supplier).filter(product_supplier.c.supplier_id == supplier_id).delete()

            # 刪除關聯的用戶
            if db_supplier.user_id:
                db.query(User).filter(User.id == db_supplier.user_id).delete()

            # 刪除供應商
            db.delete(db_supplier)
        return SuccessResponse(message="供應商刪除成功")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=error_response("DATABASE_ERROR", f"資料庫操作失敗: {str(e)}")
        )

def admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail=error_response("403_FORBIDDEN", "僅管理員可以做更動"))
    return current_user

def admin_supplier(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "supplier"]:
        raise HTTPException(status_code=403, detail=error_response("403_FORBIDDEN", "僅管理員或供應商可以做更動"))
    return current_user