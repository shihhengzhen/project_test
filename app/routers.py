from fastapi import APIRouter, Depends, HTTPException
#from sqlalchemy.orm import Session
from database import SessionLocal
#from crud import create_product, get_product, update_product, delete_product
#from schemas import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()