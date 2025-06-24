from sqlalchemy.orm import Session
from .models import Product, Supplier
from .schemas import ProductCreate, ProductUpdate

def create_product(db: Session, product: ProductCreate):
    db_product = Product(**product.dict(exclude={"supplier_ids"}))
    if product.supplier_ids:
        db_product.suppliers = db.query(Supplier).filter(Supplier.id.in_(product.supplier_ids)).all()
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

def update_product(db: Session, product_id: int, product: ProductUpdate):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    update_data = product.dict(exclude_unset=True)
    if "supplier_ids" in update_data:
        db_product.suppliers = db.query(Supplier).filter(Supplier.id.in_(update_data["supplier_ids"])).all()
        del update_data["supplier_ids"]
    for key, value in update_data.items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: int):
    db_product = get_product(db, product_id)
    if db_product:
        db.delete(db_product)
        db.commit()
    return db_product