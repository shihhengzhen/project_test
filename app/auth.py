# from fastapi import Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from jose import JWTError, jwt
# from passlib.context import CryptContext
# from datetime import datetime, timedelta
# import os
# from dotenv import load_dotenv

# load_dotenv()
# SECRET_KEY = os.getenv("SECRET_KEY")
# ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

# if not SECRET_KEY:
#     raise ValueError("SECRET_KEY environment variable is not set")
# if not ACCESS_TOKEN_EXPIRE_MINUTES:
#     raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES environment variable is not set")

# ACCESS_TOKEN_EXPIRE_MINUTES = int(ACCESS_TOKEN_EXPIRE_MINUTES)

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password):
#     return pwd_context.hash(password)

# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
#         username: str = payload.get("sub")
#         role: str = payload.get("role")
#         if username is None or role is None:
#             raise HTTPException(
#                 status_code=401,
#                 detail={
#                     "success": False,
#                     "error_code": "INVALID_TOKEN",
#                     "message": "無效的 token"
#                 }
#             )
#         return {"username": username, "role": role}
#     except JWTError:
#         raise HTTPException(
#             status_code=401,
#             detail={
#                 "success": False,
#                 "error_code": "INVALID_TOKEN",
#                 "message": "無效的 token"
#             }
#         )

# # 模擬用戶資料庫
# # fake_users_db = {
# #     "admin": {"username": "admin", "password": get_password_hash("admin123"), "role": "admin"},
# #     "supplier1": {"username": "supplier1", "password": get_password_hash("supplier123"), "role": "supplier"},
# #     "user1": {"username": "user1", "password": get_password_hash("user123"), "role": "user"}
# # }