from sqlalchemy.orm import Session
from database import get_db, Base, engine
from models import User, UserRole, Supplier, Product, product_supplier, History
from auth import get_password_hash
from sqlalchemy.sql import text

def create_test_data(db: Session):
    try:
        print("Starting to create test data...")

        # 創建所有表
        Base.metadata.create_all(bind=engine)
        print("Database tables created.")

        # 清空現有數據（按依賴順序刪除）
        db.query(History).delete()          # 先刪除 history 表
        db.query(product_supplier).delete() # 再刪除關聯表
        db.query(Product).delete()          # 再刪除產品
        db.query(Supplier).delete()         # 再刪除供應商
        db.query(User).delete()             # 最後刪除用戶
        db.commit()
        print("Existing data cleared.")

        # 插入測試用戶
        users = [
            {"username": "admin", "password": "123", "role": UserRole.admin},
            {"username": "supplier1", "password": "123", "role": UserRole.supplier},
            {"username": "user", "password": "123", "role": UserRole.user},
        ]
        for user in users:
            db_user = db.query(User).filter(User.username == user["username"]).first()
            if not db_user:
                db_user = User(
                    username=user["username"],
                    hashed_password=get_password_hash(user["password"]),
                    role=user["role"]
                )
                db.add(db_user)
        db.commit()
        print("Test users inserted.")

        # 插入測試供應商
        supplier = db.query(Supplier).filter(Supplier.id == 1).first()
        if not supplier:
            supplier = Supplier(
                id=1,
                name="TestSupplier",
                contact="contact@testsupplier.com",
                rating=4.5
            )
            db.add(supplier)
        db.commit()
        print("Test supplier inserted.")

        # 插入測試產品
        product = db.query(Product).filter(Product.id == 1).first()
        if not product:
            product = Product(
                id=1,
                name="TestProduct",
                price=100.0,
                stock=50,
                category="Electronics",
                discount=10.0
            )
            db.add(product)
        db.commit()
        print("Test product inserted.")

        # 建立產品與供應商的關聯
        db.execute(
            text("INSERT INTO product_supplier (product_id, supplier_id) VALUES (:product_id, :supplier_id) ON CONFLICT DO NOTHING"),
            {"product_id": 1, "supplier_id": 1}
        )
        db.commit()
        print("Product-supplier association created.")

        print("Test data (users, supplier, product) created successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    db = next(get_db())
    create_test_data(db)