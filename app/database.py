from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
# 用create_engine對這個DATABASE建立一個引擎
engine = create_engine(DATABASE_URL, echo = True)
# 使用sessionmaker來與資料庫建立一個對話，記得要bind=engine，這才會讓專案和資料庫連結
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# 創建SQLAlchemy的一個class，然後在其它地方使用
Base = declarative_base()

Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()