import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, engine, Base
from crud import create_product, create_supplier
from schemas import ProductCreate, SupplierCreate
from auth import get_password_hash

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def admin_token(client):
    response = client.post("/auth/login", json={"username": "admin", "password": "admin123", "role": "admin"})
    return response.json()["data"]["access_token"]

@pytest.fixture
def supplier_token(client):
    response = client.post("/auth/login", json={"username": "supplier1", "password": "supplier123", "role": "supplier"})
    return response.json()["data"]["access_token"]

@pytest.fixture
def user_token(client):
    response = client.post("/auth/login", json={"username": "user1", "password": "user123", "role": "user"})
    return response.json()["data"]["access_token"]

def test_create_product_admin(client, db, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    product_data = {
        "name": "Test Product",
        "price": 100.0,
        "stock": 50,
        "category": "電子",
        "discount": 10.0,
        "description": "Test description",
        "supplier_ids": []
    }
    response = client.post("/products/", json=product_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["data"]["name"] == "Test Product"

def test_create_product_supplier_forbidden(client, supplier_token):
    headers = {"Authorization": f"Bearer {supplier_token}"}
    product_data = {
        "name": "Test Product",
        "price": 100.0,
        "stock": 50
    }
    response = client.post("/products/", json=product_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["success"] == False
    assert response.json()["error_code"] == "FORBIDDEN"

def test_get_product_not_found(client, db, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/products/999", headers=headers)
    assert response.status_code == 404
    assert response.json()["success"] == False
    assert response.json()["error_code"] == "PRODUCT_NOT_FOUND"

def test_get_product_history_user_forbidden(client, db, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    product = create_product(db, ProductCreate(name="Test Product", price=100.0, stock=50), "admin")
    response = client.get(f"/products/{product.id}/history", headers=headers)
    assert response.status_code == 403
    assert response.json()["success"] == False
    assert response.json()["error_code"] == "FORBIDDEN"