import streamlit as st
import requests
import pandas as pd
import time
import re
from typing import Optional, Dict, Any
import plotly.express as px

# 基礎配置
BASE_URL = "http://localhost:8000"
st.set_page_config(page_title="產品管理系統", layout="wide", page_icon="📦")

# 統一錯誤處理
def handle_response(response: requests.Response) -> Optional[Dict]:
    if response.status_code in [200, 201]:
        return response.json()
    try:
        error_data = response.json()
        st.error(f"操作失敗：{error_data.get('detail', error_data.get('message', '未知錯誤'))} (錯誤碼：{error_data.get('error_code', '未知')})")
    except ValueError:
        st.error(f"操作失敗：伺服器回應錯誤 (狀態碼：{response.status_code})")
    return None

# 獲取 JWT token 的頭部
def get_auth_headers() -> Dict[str, str]:
    if "access_token" not in st.session_state:
        st.error("請先登入！")
        st.stop()
    return {"Authorization": f"Bearer {st.session_state.access_token}"}

# 檢查並刷新 token
def refresh_token_if_needed() -> bool:
    if "refresh_token" not in st.session_state:
        st.error("請重新登入！")
        st.session_state.clear()
        st.rerun()
    try:
        response = requests.post(f"{BASE_URL}/refresh", json={"refresh_token": st.session_state.refresh_token})
        data = handle_response(response)
        if data:
            st.session_state.access_token = data["access_token"]
            st.session_state.refresh_token = data["refresh_token"]
            return True
        else:
            st.session_state.clear()
            st.rerun()
    except Exception as e:
        st.error(f"刷新 token 失敗：{str(e)}")
        st.session_state.clear()
        st.rerun()
    return False

# 檢查 API 請求是否需要重試（token 過期）
def make_api_request(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    try:
        headers = kwargs.get("headers", {})
        headers.update(get_auth_headers())
        kwargs["headers"] = headers
        response = getattr(requests, method)(url, **kwargs)
        if response.status_code == 401 and response.json().get("error_code") == "INVALID_CREDENTIALS":
            if refresh_token_if_needed():
                headers.update(get_auth_headers())
                kwargs["headers"] = headers
                response = getattr(requests, method)(url, **kwargs)
        return response
    except Exception as e:
        st.error(f"API 請求失敗：{str(e)}")
        return None

# 輸入驗證函數
def validate_product_data(data: Dict[str, Any]) -> bool:
    if not data.get("name") or len(data["name"]) < 3 or len(data["name"]) > 100:
        st.error("產品名稱必須為 3-100 字元")
        return False
    if data.get("price") is not None and data["price"] < 0:
        st.error("價格必須大於或等於 0")
        return False
    if data.get("stock") is not None and data["stock"] < 0:
        st.error("庫存必須大於或等於 0")
        return False
    if data.get("discount") is not None and (data["discount"] < 0 or data["discount"] > 100):
        st.error("折扣必須在 0-100% 之間")
        return False
    return True

# 登入頁面
def login_page():
    st.title("🔒 登入")
    st.markdown("<style>.stTextInput > div > input {font-size: 16px;}</style>", unsafe_allow_html=True)
    with st.form(key="login_form"):
        username = st.text_input("用戶名", placeholder="輸入用戶名", key="login_username")
        password = st.text_input("密碼", type="password", placeholder="輸入密碼", key="login_password")
        submit_button = st.form_submit_button("登入")
        if submit_button:
            with st.spinner("正在登入..."):
                response = requests.post(
                    f"{BASE_URL}/login",
                    data={"username": username, "password": password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.access_token = data["access_token"]
                    st.session_state.refresh_token = data.get("refresh_token")
                    user_response = requests.get(
                        f"{BASE_URL}/current_user",
                        headers={"Authorization": f"Bearer {data['access_token']}"}
                    )
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        st.session_state.role = user_data.get("data", {}).get("role", "unknown")
                        st.success("登入成功！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"無法獲取用戶資訊：{user_response.status_code}")
                        handle_response(user_response)
                else:
                    handle_response(response)

# 產品篩選頁
def product_filter_page():
    st.title("📋 產品篩選")
    st.markdown("篩選並查看產品庫存", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("篩選條件")
        min_price = st.number_input("最低價格", min_value=0.0, step=0.01, format="%.2f", help="輸入最低價格")
        max_price = st.number_input("最高價格", min_value=0.0, step=0.01, format="%.2f", help="輸入最高價格")
        min_stock = st.number_input("最低庫存", min_value=0, step=1, help="輸入最低庫存量")
        max_stock = st.number_input("最高庫存", min_value=0, step=1, help="輸入最高庫存量")
        category = st.text_input("分類", placeholder="輸入分類名稱", help="輸入產品分類")
        q = st.text_input("搜尋關鍵字", placeholder="輸入產品名稱或描述", help="搜尋名稱或描述")
        limit = st.number_input("每頁顯示", min_value=1, max_value=100, value=10, step=1, help="每頁顯示的產品數")
        offset = st.number_input("偏移量", min_value=0, step=limit, value=0, help="跳過的產品數")
        order_by = st.selectbox("排序", ["", "price", "stock", "created_at"], help="選擇排序欄位")
        
        if st.button("🔍 查詢", use_container_width=True):
            with st.spinner("正在查詢..."):
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
                response = make_api_request("get", f"{BASE_URL}/product/", params=params)
                data = handle_response(response)
                if data:
                    st.session_state.products = data["product"]
                    st.session_state.total = data["total"]
                    st.success(f"查詢到 {data['total']} 個產品")

    if "products" in st.session_state:
        st.subheader("📊 數據可視化")
        df = pd.DataFrame([
            {
                "ID": p["id"],
                "名稱": p["name"],
                "價格": float(p["price"]),
                "庫存": p["stock"],
                "分類": p["category"] or "無",
                "折扣": float(p["discount"]),
                "供應商": ", ".join([s["name"] for s in p["supplier"]]) or "無",
                "建立時間": pd.to_datetime(p["created_at"]).strftime("%Y-%m-%d %H:%M:%S") if p.get("created_at") else "無",
                "更新時間": pd.to_datetime(p["updated_at"]).strftime("%Y-%m-%d %H:%M:%S") if p["updated_at"] else "無"
            } for p in st.session_state.products
        ])

        with st.expander("查看詳細統計"):
            st.markdown("**敘述統計**")
            stats = df[["價格", "庫存", "折扣"]].describe().round(2)
            stats.index = ["計數", "平均值", "標準差", "最小值", "25% 分位數", "中位數", "75% 分位數", "最大值"]
            st.dataframe(stats, use_container_width=True)

        # col1, col2 = st.columns(2)
        # with col1:
        #     if order_by in ["price", "stock", "created_at"]:
        #         if order_by == "created_at":
        #             st.markdown("**建立時間分佈**")
        #             chart_data = df[["名稱", "建立時間"]].set_index("名稱")
        #             st.bar_chart(chart_data)
        #         else:
        #             st.markdown(f"**{'價格' if order_by == 'price' else '庫存'}分佈**")
        #             chart_data = df[["名稱", "價格" if order_by == "price" else "庫存"]].set_index("名稱")
        #             st.bar_chart(chart_data)
        # with col2:
        #     st.markdown("**庫存分佈**")
        #     stock_counts = df.groupby("分類")["庫存"].sum().reset_index()
        #     stock_counts.columns = ["分類", "總庫存"]
        #     st.plotly_chart(px.pie(stock_counts, values="總庫存", names="分類", title="庫存分佈圓環圖"))

        st.subheader("產品列表")
        st.dataframe(df, use_container_width=True, height=300, hide_index=True)

def product_management_page():
    if st.session_state.role == "user":
        st.error("一般用戶無法訪問產品管理頁面！")
        st.stop()
    
    st.title("🛠 產品管理")
    st.markdown("新增、編輯或刪除產品", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("操作選擇")
        action = st.selectbox("選擇操作", ["新增產品", "編輯產品", "刪除產品"], help="選擇要執行的操作")

        if action == "新增產品":
            if st.session_state.role != "admin":
                st.error("僅管理員可以新增產品！")
                st.stop()
            with st.form(key="product_create_form"):
                name = st.text_input("名稱", max_chars=100, placeholder="輸入產品名稱", help="名稱需 3-100 字元")
                price = st.number_input("價格", min_value=0.0, step=0.01, format="%.2f", help="輸入產品價格")
                stock = st.number_input("庫存", min_value=0, step=1, help="輸入庫存數量")
                category = st.text_input("分類", placeholder="輸入分類名稱", help="可選的分類名稱")
                discount = st.number_input("折扣（%）", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", help="輸入折扣百分比")
                description = st.text_area("描述", placeholder="輸入產品描述", help="可選的產品描述")
                response = make_api_request("get", f"{BASE_URL}/supplier/")
                suppliers = handle_response(response)["supplier"] if response else []
                supplier_ids = st.multiselect(
                    "供應商",
                    options=[s["id"] for s in suppliers],
                    format_func=lambda x: f"ID: {x} - {next(s['name'] for s in suppliers if s['id'] == x)}",
                    help="選擇相關供應商"
                )
                submit_button = st.form_submit_button("✅ 提交")
                if submit_button:
                    data = {
                        "name": name,
                        "price": price,
                        "stock": stock,
                        "category": category if category else None,
                        "discount": discount,
                        "description": description if description else None,
                        "supplier_id": supplier_ids
                    }
                    if validate_product_data(data):
                        with st.spinner("正在新增..."):
                            response = make_api_request("post", f"{BASE_URL}/product/", json=data)
                            if handle_response(response):
                                st.success("新增成功！")
                                time.sleep(1)
                                st.rerun()

        elif action == "編輯產品":
            # 表單 1：載入產品資料
            with st.form(key="product_load_form"):
                product_id = st.number_input("產品 ID", min_value=1, step=1, help="輸入要編輯的產品 ID")
                load_button = st.form_submit_button("🔍 載入產品資料")
                if load_button:
                    response = make_api_request("get", f"{BASE_URL}/product/{product_id}")
                    product = handle_response(response)
                    if product:
                        st.session_state.edit_product = product
                        st.success("產品資料已載入")
                        st.rerun()
                    else:
                        st.error("無法載入產品資料，請確認產品 ID 是否正確。")

            # 表單 2：編輯產品資料
            product = st.session_state.get("edit_product", {})
            if not product:
                st.info("請先載入產品資料。")
            else:
                with st.form(key="product_edit_form"):
                    name = st.text_input(
                        "名稱",
                        value=product.get("name", ""),
                        max_chars=100,
                        placeholder="輸入產品名稱",
                        help="名稱需 3-100 字元"
                    )
                    price = st.number_input(
                        "價格",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        value=float(product.get("price", 0.0)),
                        help="輸入產品價格"
                    )
                    stock = st.number_input(
                        "庫存",
                        min_value=0,
                        step=1,
                        value=int(product.get("stock", 0)),
                        help="輸入庫存數量"
                    )
                    category = st.text_input(
                        "分類",
                        value=product.get("category", ""),
                        placeholder="輸入分類名稱",
                        help="可選的分類名稱"
                    )
                    discount = st.number_input(
                        "折扣（%）",
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        format="%.1f",
                        value=float(product.get("discount", 0.0)),
                        help="輸入折扣百分比"
                    )
                    description = st.text_area(
                        "描述",
                        value=product.get("description", ""),
                        placeholder="輸入產品描述",
                        help="可選的產品描述"
                    )
                    response = make_api_request("get", f"{BASE_URL}/supplier/")
                    suppliers = handle_response(response)["supplier"] if response else []
                    supplier_ids = st.multiselect(
                        "供應商",
                        options=[s["id"] for s in suppliers],
                        default=product.get("supplier_id", []),
                        format_func=lambda x: f"ID: {x} - {next(s['name'] for s in suppliers if s['id'] == x)}",
                        help="選擇相關供應商",
                        disabled=st.session_state.role == "supplier"
                    )
                    submit_button = st.form_submit_button("✅ 提交")
                    if submit_button:
                        data = {
                            "name": name if name else None,
                            "price": price if price != product.get("price") else None,
                            "stock": stock if stock != product.get("stock") else None,
                            "category": category if category and category != product.get("category") else None,
                            "discount": discount if discount != product.get("discount") else None,
                            "description": description if description and description != product.get("description") else None,
                            "supplier_id": supplier_ids if supplier_ids and supplier_ids != product.get("supplier_id") else None
                        }
                        data = {k: v for k, v in data.items() if v is not None}
                        if not data:
                            st.warning("未填寫任何變更！")
                            return
                        if validate_product_data(data):
                            with st.spinner("正在更新..."):
                                response = make_api_request("put", f"{BASE_URL}/product/{product_id}", json=data)
                                if handle_response(response):
                                    st.session_state.pop("edit_product", None)
                                    st.success("更新成功！")
                                    time.sleep(1)
                                    st.rerun()

        elif action == "刪除產品":
            with st.form(key="product_delete_form"):
                product_id = st.number_input("產品 ID", min_value=1, step=1, help="輸入要刪除的產品 ID")
                #confirm_delete = st.checkbox("🚨 確認刪除此產品？", key="confirm_delete_product")
                submit_button = st.form_submit_button("🗑️ 刪除")
                # if not confirm_delete:
                #     st.info("請勾選確認刪除複選框以啟用刪除按鈕")
                if submit_button : #and confirm_delete
                    if product_id <= 0:
                        st.error("請輸入有效的產品ID")
                    else:
                        with st.spinner("正在刪除..."):
                            response = make_api_request("delete", f"{BASE_URL}/product/{product_id}")
                            if response and response.status_code == 404:
                                st.error("產品 ID 不存在")
                            elif response and response.status_code == 403:
                                st.error("無權限刪除此產品")
                            elif handle_response(response):
                                st.success("刪除成功！")
                                time.sleep(1)
                                st.rerun()

# 供應商管理頁
def supplier_management_page():
    if st.session_state.role != "admin":
        st.error("僅管理員可以訪問此頁面！")
        st.stop()
    
    st.title("🏢 供應商管理")
    st.markdown("管理供應商資訊", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("供應商列表")
        response = make_api_request("get", f"{BASE_URL}/supplier/")
        suppliers = handle_response(response)["supplier"] if response else []
        if suppliers:
            df = pd.DataFrame([
                {
                    "ID": s["id"],
                    "名稱": s["name"],
                    "聯絡資訊": s["contact"] or "無",
                    "評分": f"{s['rating']:.1f} ⭐" if s["rating"] else "無",
                    "產品數": len(s["product"])
                } for s in suppliers
            ])
            st.dataframe(df, use_container_width=True, height=300, hide_index=True)

        st.subheader("操作選擇")
        action = st.selectbox("選擇操作", ["查看供應商", "新增供應商", "編輯供應商", "刪除供應商"], help="選擇要執行的操作")

        if action == "查看供應商":
            supplier_id = st.number_input("供應商 ID", min_value=1, step=1, help="輸入要查看的供應商 ID")
            if st.button("🔍 查詢", use_container_width=True):
                with st.spinner("正在查詢..."):
                    response = make_api_request("get", f"{BASE_URL}/supplier/{supplier_id}")
                    supplier = handle_response(response)
                    if supplier:
                        st.subheader("供應商詳情")
                        st.markdown(f"**ID**: {supplier['id']}")
                        st.markdown(f"**名稱**: {supplier['name']}")
                        st.markdown(f"**聯絡資訊**: {supplier['contact'] or '無'}")
                        st.markdown(f"**評分**: {supplier['rating'] or '無'} ⭐")
                        st.markdown(f"**產品數**: {len(supplier['product'])}")
                        if supplier["product"]:
                            st.markdown("**產品清單**")
                            product_df = pd.DataFrame([
                                {"產品 ID": p["id"], "產品名稱": p["name"]}
                                for p in supplier["product"]
                            ])
                            st.dataframe(product_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("此供應商目前無關聯產品")

        elif action == "新增供應商":
            with st.form(key="supplier_create_form"):
                name = st.text_input("名稱", max_chars=100, placeholder="輸入供應商名稱", help="名稱需 1-100 字元")
                contact = st.text_input("聯絡資訊", placeholder="輸入聯絡資訊", help="可選的聯絡資訊")
                rating = st.number_input("評分", min_value=0.0, max_value=5.0, step=0.1, format="%.1f", help="輸入 0-5 的評分")
                submit_button = st.form_submit_button("✅ 提交")
                if submit_button:
                    if not name or len(name) > 100:
                        st.error("供應商名稱必須為 1-100 字元")
                        return
                    if rating < 0 or rating > 5:
                        st.error("評分必須在 0-5 之間")
                        return
                    with st.spinner("正在新增..."):
                        data = {
                            "name": name,
                            "contact": contact if contact else None,
                            "rating": rating if rating > 0 else None
                        }
                        response = make_api_request("post", f"{BASE_URL}/supplier/", json=data)
                        if handle_response(response):
                            st.success(f"新增成功！自動生成用戶帳號：supplier_{response.json()['id']}")
                            time.sleep(1)
                            st.rerun()

        elif action == "編輯供應商":
            with st.form(key="supplier_edit_form"):
                supplier_id = st.number_input("供應商 ID", min_value=1, step=1, help="輸入要編輯的供應商 ID")
                load_button = st.form_submit_button("🔍 載入供應商資料")
                if load_button:
                    response = make_api_request("get", f"{BASE_URL}/supplier/{supplier_id}")
                    supplier = handle_response(response)
                    if supplier:
                        st.session_state.edit_supplier = supplier
                        st.success("供應商資料已載入")
                        st.rerun()

                supplier = st.session_state.get("edit_supplier", {})
                if not supplier:
                    st.info("請先載入供應商資料。")
                else:
                    name = st.text_input(
                        "名稱",
                        value=supplier.get("name", ""),
                        max_chars=100,
                        placeholder="輸入供應商名稱",
                        help="名稱需 1-100 字元"
                    )
                    contact = st.text_input(
                        "聯絡資訊",
                        value=supplier.get("contact", ""),
                        placeholder="輸入聯絡資訊",
                        help="可選的聯絡資訊"
                    )
                    rating = st.number_input(
                        "評分",
                        min_value=0.0,
                        max_value=5.0,
                        step=0.1,
                        format="%.1f",
                        value=float(supplier.get("rating", 0.0)),
                        help="輸入 0-5 的評分"
                    )
                    submit_button = st.form_submit_button("✅ 提交")
                    if submit_button:
                        if not name or len(name) > 100:
                            st.error("供應商名稱必須為 1-100 字元")
                            return
                        if rating < 0 or rating > 5:
                            st.error("評分必須在 0-5 之間")
                            return
                        data = {
                            "name": name if name and name != supplier.get("name") else None,
                            "contact": contact if contact and contact != supplier.get("contact") else None,
                            "rating": rating if rating and rating != supplier.get("rating") else None
                        }
                        data = {k: v for k, v in data.items() if v is not None}
                        if not data:
                            st.warning("未填寫任何變更！")
                            return
                        with st.spinner("正在更新..."):
                            response = make_api_request("put", f"{BASE_URL}/supplier/{supplier_id}", json=data)
                            if handle_response(response):
                                st.session_state.pop("edit_supplier", None)
                                st.success("更新成功！")
                                time.sleep(1)
                                st.rerun()

        elif action == "刪除供應商":
            with st.form(key="supplier_delete_form"):
                supplier_id = st.number_input("供應商 ID", min_value=1, step=1, help="輸入要刪除的供應商 ID")
                #confirm_delete = st.checkbox("🚨 確認刪除此供應商？（此操作無法復原）", key="confirm_delete_supplier")
                submit_button = st.form_submit_button("🗑️ 刪除")
                # if not confirm_delete:
                #     st.info("請勾選確認刪除複選框以啟用刪除按鈕")
                if submit_button : #and confirm_delete
                    with st.spinner("正在刪除..."):
                        response = make_api_request("delete", f"{BASE_URL}/supplier/{supplier_id}")
                        if response and response.status_code == 404:
                            st.error("供應商 ID 不存在")
                        elif response and response.status_code == 403:
                            st.error("無權限刪除此供應商")
                        elif handle_response(response):
                            st.success("刪除成功！")
                            time.sleep(1)
                            st.rerun()

# 歷史記錄頁，沒有變更紀錄的
def history_page():
    if st.session_state.role not in ["admin", "supplier"]:
        st.error("僅管理員或供應商可以訪問此頁面！")
        st.stop()
    
    st.title("📜 產品歷史記錄")
    st.markdown("查詢產品的價格和庫存變動歷史", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("查詢條件")
        with st.form(key="history_form"):
            product_id = st.number_input("產品 ID", min_value=1, step=1, help="輸入要查詢的產品 ID")
            start_date = st.date_input("開始日期", value=None, help="選擇開始日期（可選）")
            end_date = st.date_input("結束日期", value=None, help="選擇結束日期（可選）")
            submit_button = st.form_submit_button("🔍 查詢")
            if submit_button:
                with st.spinner("正在查詢..."):
                    params = {
                        "start_date": start_date.isoformat() if start_date else None,
                        "end_date": end_date.isoformat() if end_date else None
                    }
                    response = make_api_request("get", f"{BASE_URL}/product/{product_id}/history", params=params)
                    history = handle_response(response)
                    if history:
                        st.session_state.history = history
                        st.success("查詢成功！")

        if "history" in st.session_state and st.session_state.history:
            st.subheader(f"產品 ID: {st.session_state.history[0]['product_id']} - {st.session_state.history[0]['product_name']}")
            df = pd.DataFrame([
                {
                    "時間": pd.to_datetime(h["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "欄位": "📈 價格" if h["field"] == "price" else "📦 庫存",
                    "舊值": f"{h['old_value']:.2f}" if h["old_value"] is not None else "無",
                    "新值": f"{h['new_value']:.2f}" if h["new_value"] is not None else "無",
                    "變動者": h["changed_by"] or "未知",
                    "變動類型": "🔼 增加" if h["new_value"] > h["old_value"] else "🔽 減少" if h["new_value"] < h["old_value"] else "無變動"
                } for h in st.session_state.history
            ])
            if not df.empty:
                df["時間"] = pd.to_datetime(df["時間"])
                price_data = df[df["欄位"] == "📈 價格"]
                stock_data = df[df["欄位"] == "📦 庫存"]

                if not price_data.empty:
                    st.subheader("價格變動趨勢")
                    st.line_chart(price_data[["時間", "新值"]].set_index("時間").rename(columns={"新值": "價格"}))
                    st.subheader("價格歷史記錄")
                    st.dataframe(price_data[["時間", "舊值", "新值", "變動者", "變動類型"]], use_container_width=True, height=200)

                if not stock_data.empty:
                    st.subheader("庫存變動趨勢")
                    st.line_chart(stock_data[["時間", "新值"]].set_index("時間").rename(columns={"新值": "庫存"}))
                    st.subheader("庫存歷史記錄")
                    st.dataframe(stock_data[["時間", "舊值", "新值", "變動者", "變動類型"]], use_container_width=True, height=200)

# 批量操作頁
def batch_operation_page():
    if st.session_state.role != "admin":
        st.error("僅管理員可以訪問此頁面！")
        st.stop()
    
    st.title("🔄 批量操作")
    st.markdown("批量管理多個產品", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("操作選擇")
        action = st.selectbox("選擇操作", ["批量新增", "批量刪除"], help="選擇要執行的批量操作")

        if action == "批量新增":
            st.markdown("**輸入產品資料（每行一個產品）**")
            st.markdown("""
            <small>格式示例：</small>
            <pre>
            名稱: 產品A, 價格: 100.0, 庫存: 50, 分類: Electronics, 折扣: 10.0, 描述: 描述A, 供應商ID: [1;2]
            名稱: 產品B, 價格: 200.0, 庫存: 30, 分類: Clothing, 折扣: 5.0, 描述: 描述B, 供應商ID: [1]
            </pre>
            """, unsafe_allow_html=True)
            response = make_api_request("get", f"{BASE_URL}/supplier/")
            suppliers = handle_response(response)["supplier"] if response else []
            supplier_options = {s["id"]: s["name"] for s in suppliers}

            if "batch_data" not in st.session_state:
                st.session_state.batch_data = pd.DataFrame(columns=[
                    "名稱", "價格", "庫存", "分類", "折扣", "描述", "供應商ID"
                ])

            edited_df = st.data_editor(
                st.session_state.batch_data,
                num_rows="dynamic",
                column_config={
                    "名稱": st.column_config.TextColumn(required=True, max_chars=100),
                    "價格": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.2f", required=True),
                    "庫存": st.column_config.NumberColumn(min_value=0, step=1, required=True),
                    "分類": st.column_config.TextColumn(required=False),
                    "折扣": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.1, format="%.1f", required=True),
                    "描述": st.column_config.TextColumn(required=False),
                    "供應商ID": st.column_config.TextColumn(
                        help="輸入供應商 ID，格式為 [1;2]，用分號分隔"
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            st.session_state.batch_data = edited_df

            if st.button("✅ 提交批量新增"):
                products = []
                for _, row in edited_df.iterrows():
                    if not row["名稱"] or pd.isna(row["名稱"]):
                        st.error("每行必須包含名稱")
                        return
                    try:
                        supplier_ids = []
                        if row["供應商ID"] and pd.notna(row["供應商ID"]):
                            supplier_ids = [int(s) for s in row["供應商ID"].strip("[]").split(";") if s]
                            for sid in supplier_ids:
                                if sid not in supplier_options:
                                    st.error(f"無效的供應商 ID: {sid}")
                                    return
                        products.append({
                            "name": row["名稱"],
                            "price": float(row["價格"]),
                            "stock": int(row["庫存"]),
                            "category": row["分類"] if pd.notna(row["分類"]) else None,
                            "discount": float(row["折扣"]),
                            "description": row["描述"] if pd.notna(row["描述"]) else None,
                            "supplier_id": supplier_ids
                        })
                    except (ValueError, TypeError):
                        st.error(f"資料格式錯誤：{row['名稱']}")
                        return
                if products and all(validate_product_data(p) for p in products):
                    with st.spinner("正在批量新增..."):
                        response = make_api_request("post", f"{BASE_URL}/product/batch_create", json={"product": products})
                        if handle_response(response):
                            st.session_state.batch_data = pd.DataFrame(columns=st.session_state.batch_data.columns)
                            st.success("批量新增成功！")
                            time.sleep(1)
                            st.rerun()

        elif action == "批量刪除":
            with st.form(key="batch_delete_form"):
                # 獲取產品清單
                response = make_api_request("get", f"{BASE_URL}/product/")
                products = handle_response(response)["product"] if response else []
                
                # 檢查產品清單是否為空
                if not products:
                    st.warning("目前無產品可刪除，請先新增產品")
                    st.stop()
                
                selected_ids = st.multiselect(
                    "選擇要刪除的產品",
                    options=[p["id"] for p in products],
                    format_func=lambda x: f"ID: {x} - {next(p['name'] for p in products if p['id'] == x)}",
                    help="選擇要刪除的產品"
                )
                confirm_delete = st.checkbox("🚨 確認刪除選中的產品？（此操作無法復原）", key="confirm_batch_delete")
                submit_button = st.form_submit_button("🗑️ 刪除")
                
                # 用戶提示
                # if not confirm_delete:
                #     st.info("請勾選確認刪除複選框以啟用刪除按鈕")
                # if not selected_ids:
                #     st.info("請至少選擇一個產品進行刪除")
                
                # 提交邏輯
                if submit_button and confirm_delete and selected_ids:
                    with st.spinner("正在批量刪除..."):
                        # 假設正確的批量刪除端點為 /product/batch/delete
                        response = make_api_request("delete", f"{BASE_URL}/product/batch/delete", json={"ids": selected_ids})
                        if response and response.status_code == 400:
                            try:
                                error_detail = response.json().get("detail", "未知錯誤")
                                st.error(f"批量刪除失敗：{error_detail}")
                            except ValueError:
                                st.error("批量刪除失敗：無效的回應格式")
                        elif response and response.status_code == 404:
                            st.error("部分產品 ID 不存在")
                        elif response and response.status_code == 403:
                            st.error("無權限刪除選中的產品")
                        elif handle_response(response):
                            st.success("批量刪除成功！")
                            time.sleep(1)
                            st.rerun()
                
                # 調試用：顯示當前狀態
                st.write(f"調試資訊：複選框狀態 = {confirm_delete}, 選擇的產品 ID = {selected_ids}")

# 主邏輯
if __name__ == "__main__":
    if "access_token" not in st.session_state:
        login_page()
    else:
        with st.sidebar:
            st.title("🛒 產品管理系統")
            st.markdown(f"**當前角色**：{st.session_state.role}")
            if st.button("🚪 登出"):
                st.session_state.clear()
                st.rerun()
            
            pages = ["產品篩選"]
            if st.session_state.role in ["admin", "supplier"]:
                pages.extend(["產品管理", "歷史記錄"])
            if st.session_state.role == "admin":
                pages.extend(["供應商管理", "批量操作"])
            page = st.selectbox("選擇頁面", pages, help="選擇要操作的功能")

        if page == "產品篩選":
            product_filter_page()
        elif page == "產品管理":
            product_management_page()
        elif page == "供應商管理":
            supplier_management_page()
        elif page == "歷史記錄":
            history_page()
        elif page == "批量操作":
            batch_operation_page()