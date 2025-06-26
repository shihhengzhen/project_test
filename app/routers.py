from fastapi import APIRouter, Depends, HTTPException
#from sqlalchemy.orm import Session
from database import SessionLocal
from crud import create_product, get_product, update_product, delete_product
#from schemas import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# @router.post("/products/", response_model=ProductResponse)
# def create_product_api(product: ProductCreate, db: Session = Depends(get_db)):
#     return create_product(db, product)
# @router.post("/products/", response_model=ProductResponse)
# def create_product_api(product: ProductCreate, db: Session = Depends(get_db)):
#     try:
#         return create_product(db, product)
#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=500, detail=str(e))
# @router.get("/products/{id}", response_model=ProductResponse)
# def read_product(id: int, db: Session = Depends(get_db)):
#     product = get_product(db, id)
#     if not product:
#         raise HTTPException(status_code=404, detail="Product is not found")
#     return product

# @router.put("/products/{id}", response_model=ProductResponse)
# def update_product_api(id: int, product: ProductUpdate, db: Session = Depends(get_db)):
#     updated_product = update_product(db, id, product)
#     if not updated_product:
#         raise HTTPException(status_code=404, detail="Product is not found")
#     return updated_product

# @router.delete("/products/{id}")
# def delete_product_api(id: int, db: Session = Depends(get_db)):
#     product = delete_product(db, id)
#     if not product:
#         raise HTTPException(status_code=404, detail="Product is not found")
#     return {"success": True}