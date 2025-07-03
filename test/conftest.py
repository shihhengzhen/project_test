import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.database import Base, get_db
from app.main import app
from app.models import User, Supplier, Product, History
from app.auth import get_password_hash, create_access_token
from unittest.mock import patch

# 使用 SQLite 記憶體資料庫進行測試
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def admin_user(db):
    user = User(
        username="admin_user",
        hashed_password=get_password_hash("admin123"),
        role="admin"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def supplier_user(db):
    user = User(
        username="supplier_1",
        hashed_password=get_password_hash("supplier123"),
        role="supplier"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    supplier = Supplier(
        id=1,
        name="Supplier 1",
        contact="contact@supplier1.com",
        user_id=user.id
    )
    db.add(supplier)
    db.commit()
    return user

@pytest.fixture
def regular_user(db):
    user = User(
        username="regular_user",
        hashed_password=get_password_hash("user123"),
        role="user"
    )
    db.add(user)
    db.commit()
    return user

@pytest.fixture
def admin_token(admin_user):
    return create_access_token({"sub": admin_user.username, "role": admin_user.role})

@pytest.fixture
def supplier_token(supplier_user):
    return create_access_token({"sub": supplier_user.username, "role": supplier_user.role})

@pytest.fixture
def user_token(regular_user):
    return create_access_token({"sub": regular_user.username, "role": regular_user.role})

@pytest.fixture
def test_product(db, supplier_user):
    supplier = db.query(Supplier).filter(Supplier.user_id == supplier_user.id).first()
    product = Product(
        id=1,
        name="Test Product",
        price=100.0,
        description="Test Description",
        stock=10,
        category="Test Category",
        discount=0.0
    )
    product.supplier.append(supplier)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product