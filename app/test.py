from sqlalchemy.orm import Session
from database import get_db, Base, engine
from models import User, UserRole, Supplier, Product, product_supplier, History
from auth import get_password_hash
from sqlalchemy.sql import text

def create_test_data(db: Session):
    try:
        Base.metadata.create_all(bind=engine)
        db.query(History).delete()         
        db.query(product_supplier).delete() 
        db.query(Product).delete()          
        db.query(Supplier).delete()        
        db.query(User).delete()            
        db.commit()
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
        db.execute(
            text("INSERT INTO product_supplier (product_id, supplier_id) VALUES (:product_id, :supplier_id) ON CONFLICT DO NOTHING"),
            {"product_id": 1, "supplier_id": 1}
        )
        db.commit()

        print("測試資料加入成功")
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    db = next(get_db())
    create_test_data(db)