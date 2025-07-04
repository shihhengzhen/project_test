import pytest
import asyncio
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Product, Supplier, History, User
from app.schemas import ProductCreate, ProductUpdate, SupplierCreate
from unittest.mock import patch
import json
#pytest --cov=app --cov-report=html tests/
#pip install pytest pytest-asyncio pytest-cov httpx pytest-mock
@pytest.mark.asyncio
async def test_create_product_as_admin(client: TestClient, db: Session, admin_token):
    product_data = {
        "name": "New Product",
        "price": 50.0,
        "description": "A new product",
        "stock": 20,
        "category": "Electronics",
        "discount": 10.0,
        "supplier_id": [1]
    }
    response = client.post(
        "/product/",
        json=product_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "產品創建成功"}
    product = db.query(Product).filter(Product.name == "New Product").first()
    assert product is not None
    assert product.price == 50.0

@pytest.mark.asyncio
async def test_create_product_as_supplier(client: TestClient, db: Session, supplier_token, supplier_user):
    product_data = {
        "name": "Supplier Product",
        "price": 30.0,
        "description": "Supplier's product",
        "stock": 15,
        "category": "Clothing",
        "discount": 5.0
    }
    response = client.post(
        "/product/",
        json=product_data,
        headers={"Authorization": f"Bearer {supplier_token}"}
    )
    assert response.status_code == 200
    product = db.query(Product).filter(Product.name == "Supplier Product").first()
    assert product is not None
    supplier = db.query(Supplier).filter(Supplier.user_id == supplier_user.id).first()
    assert supplier.id in [s.id for s in product.supplier]

@pytest.mark.asyncio
async def test_create_product_as_user(client: TestClient, user_token):
    product_data = {
        "name": "Invalid Product",
        "price": 10.0,
        "stock": 5
    }
    response = client.post(
        "/product/",
        json=product_data,
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "403_FORBIDDEN"

@pytest.mark.asyncio
async def test_read_product_anonymous(client: TestClient, test_product):
    response = client.get("/product/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Product"

@pytest.mark.asyncio
async def test_read_product_not_found(client: TestClient):
    response = client.get("/product/999")
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "PRODUCT_NOT_FOUND"

@pytest.mark.asyncio
async def test_update_product_as_supplier(client: TestClient, db: Session, supplier_token, test_product):
    update_data = {
        "name": "Updated Product",
        "price": 150.0,
        "stock": 25,
        "description": "Updated Description",
        "category": "Updated Category",
        "discount": 15.0
    }
    response = client.put(
        "/product/1",
        json=update_data,
        headers={"Authorization": f"Bearer {supplier_token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "產品更新成功"}
    db.refresh(test_product)
    assert test_product.name == "Updated Product"
    assert test_product.price == 150.0
    history = db.query(History).filter(History.product_id == 1).all()
    assert len(history) == 2  # price and stock changes
    assert history[0].changed_by == "supplier_1"

@pytest.mark.asyncio
async def test_update_product_supplier_id_as_supplier(client: TestClient, supplier_token, test_product):
    update_data = {
        "price": 200.0,
        "supplier_id": [1]
    }
    response = client.put(
        "/product/1",
        json=update_data,
        headers={"Authorization": f"Bearer {supplier_token}"}
    )
    assert response.status_code == 200  # supplier_id ignored
    assert response.json() == {"success": True, "message": "產品更新成功"}

@pytest.mark.asyncio
async def test_update_product_as_user(client: TestClient, test_product, user_token):
    update_data = {"name": "Invalid Update"}
    response = client.put(
        "/product/1",
        json=update_data,
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "403_FORBIDDEN"

@pytest.mark.asyncio
async def test_delete_product_as_admin(client: TestClient, db: Session, admin_token, test_product):
    response = client.delete(
        "/product/1",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "產品刪除成功"}
    product = db.query(Product).filter(Product.id == 1).first()
    assert product is None

@pytest.mark.asyncio
async def test_create_supplier_as_admin(client: TestClient, db: Session, admin_token):
    supplier_data = {
        "name": "New Supplier",
        "contact": "new@supplier.com",
        "rating": 4.5
    }
    response = client.post(
        "/supplier/",
        json=supplier_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    supplier = db.query(Supplier).filter(Supplier.name == "New Supplier").first()
    assert supplier is not None
    user = db.query(User).filter(User.username == f"supplier_{supplier.id}").first()
    assert user is not None
    assert user.role == "supplier"

@pytest.mark.asyncio
async def test_supplier_cannot_create_supplier(client: TestClient, supplier_token):
    supplier_data = {"name": "Invalid Supplier"}
    response = client.post(
        "/supplier/",
        json=supplier_data,
        headers={"Authorization": f"Bearer {supplier_token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "403_FORBIDDEN"

@pytest.mark.asyncio
async def test_high_concurrency_read(client: TestClient, test_product):
    async def make_request():
        async with httpx.AsyncClient() as async_client:
            response = await async_client.get(
                "http://127.0.0.1:8000/product/1",
                headers={"accept": "application/json"}
            )
            return response.status_code

    tasks = [make_request() for _ in range(100)]
    results = await asyncio.gather(*tasks)
    assert all(status == 200 for status in results)

@pytest.mark.asyncio
async def test_invalid_price(client: TestClient, admin_token):
    product_data = {
        "name": "Invalid Product",
        "price": -10.0,  
        "stock": 5
    }
    response = client.post(
        "/product/",
        json=product_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422
    assert "ensure this value is greater than or equal to 0" in response.text

@patch("app.auth.jwt.decode")
def test_invalid_token(mock_jwt_decode, client: TestClient):
    mock_jwt_decode.side_effect = Exception("Invalid token")
    response = client.get(
        "/product/1",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"