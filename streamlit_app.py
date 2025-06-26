import streamlit as st
import requests
import pandas as pd
from datetime import datetime

BASE_URL = "http://localhost:8000"

# 設置頁面配置
st.set_page_config(page_title="產品管理系統", layout="wide")

# 會話狀態管理
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "username" not in st.session_state:
    st.session_state.username = None

# 統一錯誤處理
def handle_response(response):
    if response.status_code in [200, 201]:
        return response.json()["data"]
    else:
        st.error(response.json().get("message", "操作失敗"))
        return None

# 登入介面
def login_page():
    st.title("登入")
    username = st.text_input("帳號")
    password = st.text_input("密碼", type="password")
    role = st.selectbox("角色", ["admin", "supplier", "user"])
    if st.button("登入"):
        response = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password, "role": role})
        data = handle_response(response)
        if data:
            st.session_state.token = data["access_token"]
            st.session_state.role = role
            st.session_state.username = username
            st.success("登入成功！")
            st.rerun()

# 產品清單頁
def product_list_page():
    st.title("產品清單")
    col1, col2 = st.columns([3, 1])
    with col1:
        min_price = st.number_input("最低價格", min_value=0.0, step=0.01)
        max_price = st.number_input("最高價格", min_value=0.0, step=0.01)
        min_stock = st.number_input("最低庫存", min_value=0, step=1)
        max_stock = st.number_input("最高庫存", min_value=0, step=1)
        category = st.text_input("分類")
        q = st.text_input("搜尋關鍵字")
        limit = st.number_input("每頁顯示", min_value=1, max_value=100, value=10)
        offset = st.number_input("偏移量", min_value=0, step=limit, value=0)
        order_by = st.selectbox("排序", ["", "price", "stock", "created_at"])
    with col2:
        if st.button("查詢"):
            params = {
                "min_price": min_price if min_price > 0 else None,
                "max_price": max_price if max_price > 0 else None,
                "min_stock": min_stock if min_stock > 0 else None,
                "max_stock": max_stock if max_stock > 0 else None,
                "category": category if category else None,
                "q": q if q else None,
                "limit": limit,
                "offset": offset,
                "order_by": order_by if order_by else None
            }
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = requests.get(f"{BASE_URL}/products/", params=params, headers=headers)
            data = handle_response(response)
            if data:
                st.session_state.products = data["products"]
                st.session_state.total = data["total"]
    
    if "products" in st.session_state:
        df = pd.DataFrame([
            {
                "ID": p["id"],
                "名稱": p["name"],
                "價格": p["price"],
                "庫存": p["stock"],
                "分類": p["category"],
                "折扣": p["discount"],
                "供應商": ", ".join([s["name"] for s in p["suppliers"]]),
                "更新時間": p["updated_at"]
            } for p in st.session_state.products
        ])
        st.dataframe(df)
        if st.session_state.role == "admin":
            selected_ids = st.multiselect("選擇要刪除的產品 ID", [p["ID"] for p in st.session_state.products])
            if st.button("批量刪除"):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                response = requests.delete(f"{BASE_URL}/products/batch_delete", json={"ids": selected_ids}, headers=headers)
                if handle_response(response):
                    st.success("刪除成功！")
                    st.rerun()

# 產品新增/編輯頁
def product_edit_page():
    st.title("新增/編輯產品")
    product_id = st.number_input("產品 ID（編輯時填寫）", min_value=0, step=1)
    name = st.text_input("名稱", max_chars=100)
    price = st.number_input("價格", min_value=0.0, step=0.01)
    stock = st.number_input("庫存", min_value=0, step=1)
    category = st.text_input("分類")
    discount = st.number_input("折扣（%）", min_value=0.0, max_value=100.0, step=0.1)
    description = st.text_area("描述")
    response = requests.get(f"{BASE_URL}/suppliers/", headers={"Authorization": f"Bearer {st.session_state.token}"})
    suppliers = handle_response(response)["suppliers"] if response.status_code == 200 else []
    supplier_ids = st.multiselect("供應商", [s["id"] for s in suppliers], format_func=lambda x: next(s["name"] for s in suppliers if s["id"] == x))
    
    if st.button("提交"):
        data = {
            "name": name,
            "price": price,
            "stock": stock,
            "category": category if category else None,
            "discount": discount,
            "description": description if description else None,
            "supplier_ids": supplier_ids
        }
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        if product_id:
            data["id"] = product_id
            response = requests.put(f"{BASE_URL}/products/{product_id}", json=data, headers=headers)
        else:
            response = requests.post(f"{BASE_URL}/products/", json=data, headers=headers)
        if handle_response(response):
            st.success("操作成功！")

# 供應商管理頁
def supplier_management_page():
    st.title("供應商管理")
    response = requests.get(f"{BASE_URL}/suppliers/", headers={"Authorization": f"Bearer {st.session_state.token}"})
    suppliers = handle_response(response)["suppliers"] if response.status_code == 200 else []
    if suppliers:
        df = pd.DataFrame([
            {
                "ID": s["id"],
                "名稱": s["name"],
                "聯絡資訊": s["contact"],
                "評分": s["rating"],
                "產品數": len(s["products"])
            } for s in suppliers
        ])
        st.dataframe(df)
    
    st.subheader("新增/編輯供應商")
    supplier_id = st.number_input("供應商 ID（編輯時填寫）", min_value=0, step=1)
    name = st.text_input("名稱", max_chars=100)
    contact = st.text_input("聯絡資訊")
    rating = st.number_input("評分", min_value=0.0, max_value=5.0, step=0.1)
    if st.button("提交"):
        data = {"name": name, "contact": contact if contact else None, "rating": rating if rating else None}
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        if supplier_id:
            response = requests.put(f"{BASE_URL}/suppliers/{supplier_id}", json=data, headers=headers)
        else:
            response = requests.post(f"{BASE_URL}/suppliers/", json=data, headers=headers)
        if handle_response(response):
            st.success("操作成功！")
            st.rerun()

# 歷史記錄頁
def history_page():
    st.title("產品歷史記錄")
    product_id = st.number_input("產品 ID", min_value=1, step=1)
    start_date = st.date_input("開始日期")
    end_date = st.date_input("結束日期")
    if st.button("查詢"):
        params = {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(f"{BASE_URL}/products/{product_id}/history", params=params, headers=headers)
        history = handle_response(response)
        if history:
            df = pd.DataFrame([
                {
                    "時間": h["timestamp"],
                    "欄位": h["field"],
                    "舊值": h["old_value"],
                    "新值": h["new_value"],
                    "變動者": h["changed_by"]
                } for h in history
            ])
            st.dataframe(df)
            if not df.empty:
                df["時間"] = pd.to_datetime(df["時間"])
                price_data = df[df["欄位"] == "price"]
                stock_data = df[df["欄位"] == "stock"]
                if not price_data.empty:
                    st.line_chart(price_data[["時間", "新值"]].set_index("時間").rename(columns={"新值": "價格"}))
                if not stock_data.empty:
                    st.line_chart(stock_data[["時間", "新值"]].set_index("時間").rename(columns={"新值": "庫存"}))

# 主邏輯
if not st.session_state.token:
    login_page()
else:
    st.sidebar.title(f"歡迎，{st.session_state.username} ({st.session_state.role})")
    page = st.sidebar.selectbox("選擇頁面", ["產品清單", "新增/編輯產品", "供應商管理", "歷史記錄"])
    if st.sidebar.button("登出"):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.username = None
        st.rerun()
    
    if page == "產品清單":
        product_list_page()
    elif page == "新增/編輯產品" and st.session_state.role in ["admin", "supplier"]:
        product_edit_page()
    elif page == "供應商管理" and st.session_state.role == "admin":
        supplier_management_page()
    elif page == "歷史記錄" and st.session_state.role in ["admin", "supplier"]:
        history_page()