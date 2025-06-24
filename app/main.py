from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .schemas import ProductCreate, ProductResponse, ProductUpdate
from .crud import create_product, get_product, update_product, delete_product
from fastapi import APIRouter
from pydantic import BaseModel
from .auth import get_current_user

app = FastAPI()
router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str

@app.post("/products/", response_model=ProductResponse)
def create_product_api(product: ProductCreate, db: Session = Depends(get_db)):
    return create_product(db, product)

@app.get("/products/{id}", response_model=ProductResponse)
def read_product(id: int, db: Session = Depends(get_db)):
    product = get_product(db, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{id}", response_model=ProductResponse)
def update_product_api(id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    updated_product = update_product(db, id, product)
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated_product

@app.delete("/products/{id}")
def delete_product_api(id: int, db: Session = Depends(get_db)):
    product = delete_product(db, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"success": True}

# 假設簡單的用戶資料庫（實際應使用資料庫）
fake_users_db = {
    "admin": {"username": "admin", "password": get_password_hash("admin123"), "role": "admin"},
    "supplier": {"username": "supplier", "password": get_password_hash("supplier123"), "role": "supplier"},
    "user": {"username": "user", "password": get_password_hash("user123"), "role": "user"}
}

@router.post("/auth/login")
def login(request: LoginRequest):
    user = fake_users_db.get(request.username)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}
app.include_router(router)

@app.post("/products/", response_model=ProductResponse)
def create_product_api(product: ProductCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return create_product(db, product)