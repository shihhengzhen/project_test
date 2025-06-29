import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.auth import create_access_token
from app.models import User, UserRole
import random
import httpx

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def admin_token():
    return create_access_token({"sub": "admin_user", "role": "admin"})

@pytest.fixture
def supplier_token():
    return create_access_token({"sub": "supplier_user", "role": "supplier"})

@pytest.fixture
def user_token():
    return create_access_token({"sub": "regular_user", "role": "user"})

def test_create_product_admin(setup_database, admin_token):
    response = client.post(
        "/product/",
        json={
            "name": "Test Product",
            "price": 99.99,
            "stock": 100,
            "category": "Electronics",
            "discount": 10.0,
            "supplier_id": [1]
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Test Product"

def test_create_product_unauthorized(user_token):
    response = client.post(
        "/product/",
        json={
            "name": "Test Product",
            "price": 99.99,
            "stock": 100
        },
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "PERMISSION_DENIED"

def test_get_product_list(setup_database, user_token):
    response = client.get("/product/", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200
    assert "product" in response.json()
    assert "total" in response.json()

def test_concurrent_product_create(setup_database, admin_token):
    import asyncio
    async def create_product():
        async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
            response = await async_client.post(
                "/product/",
                json={
                    "name": f"Test Product {random.randint(1, 1000)}",
                    "price": 99.99,
                    "stock": 100,
                    "category": "Electronics"
                },
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            return response.status_code
    tasks = [create_product() for _ in range(50)]
    results = asyncio.run(asyncio.gather(*tasks))
    assert all(status == 200 for status in results)

def test_coverage():
    # 執行 pytest-cov
    # 在終端機執行: pytest --cov=. --cov-report=html
    pass