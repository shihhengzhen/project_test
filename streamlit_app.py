import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

# 基礎配置
BASE_URL = "http://localhost:8000"
st.set_page_config(page_title="產品管理系統", layout="wide", page_icon="📦")

# 統一錯誤處理
def handle_response(response):
    if response.status_code in [200, 201]:
        return response.json()
    else:
        st.error(f"操作失敗：{response.json().get('message', '未知錯誤')}")
        return None

# 產品篩選頁
def product_filter_page():
    st.title("📋 產品篩選")
    st.markdown("篩選並查看產品庫存")
    with st.container():
        st.subheader("篩選條件")
        col1, col2 = st.columns([3, 1])
        with col1:
            min_price = st.number_input("最低價格", min_value=0.0, step=0.01, format="%.2f", help="輸入最低價格")
            max_price = st.number_input("最高價格", min_value=0.0, step=0.01, format="%.2f", help="輸入最高價格")
            min_stock = st.number_input("最低庫存", min_value=0, step=1, help="輸入最低庫存量")
            max_stock = st.number_input("最高庫存", min_value=0, step=1, help="輸入最高庫存量")
            category = st.text_input("分類", placeholder="輸入分類名稱", help="輸入產品分類")
            q = st.text_input("搜尋關鍵字", placeholder="輸入產品名稱或描述", help="搜尋名稱或描述")
            limit = st.number_input("每頁顯示", min_value=1, max_value=100, value=10, step=1, help="每頁顯示的產品數")
            offset = st.number_input("偏移量", min_value=0, step=limit, value=0, help="跳過的產品數")
            order_by = st.selectbox("排序", ["", "price", "stock", "created_at"], help="選擇排序欄位")
        with col2:
            if st.button("查詢", use_container_width=True):
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
                    response = requests.get(f"{BASE_URL}/product/", params=params)
                    data = handle_response(response)
                    if data:
                        st.session_state.products = data["product"]
                        st.session_state.total = data["total"]
                        st.success(f"查詢到 {data['total']} 個產品")
    
    if "products" in st.session_state:
        st.subheader("產品列表")
        df = pd.DataFrame([
            {
                "ID": p["id"],
                "名稱": p["name"],
                "價格": f"{p['price']:.2f}",
                "庫存": p["stock"],
                "分類": p["category"] or "無",
                "折扣": f"{p['discount']:.1f}%",
                "供應商": ", ".join([s["name"] for s in p["supplier"]]) or "無",
                "更新時間": pd.to_datetime(p["updated_at"]).strftime("%Y-%m-%d %H:%M:%S") if p["updated_at"] else "無"
            } for p in st.session_state.products
        ])
        st.dataframe(df, use_container_width=True, height=300)
        
        if order_by in ["price", "stock"]:
            st.subheader(f"{order_by.capitalize()} 長條圖")
            chart_data = df[["名稱", order_by.capitalize()]].set_index("名稱")
            chart_data[order_by.capitalize()] = chart_data[order_by.capitalize()].astype(float)
            st.bar_chart(chart_data)

# 產品管理頁
def product_management_page():
    st.title("🛠 產品管理")
    st.markdown("新增、編輯或刪除產品")
    with st.container():
        st.subheader("操作選擇")
        action = st.selectbox("選擇操作", ["新增產品", "編輯產品", "刪除產品"], help="選擇要執行的操作")
        
        if action == "新增產品":
            with st.form(key="product_create_form"):
                name = st.text_input("名稱", max_chars=100, placeholder="輸入產品名稱", help="名稱需 3-100 字元")
                price = st.number_input("價格", min_value=0.01, step=0.01, format="%.2f", help="輸入產品價格")
                stock = st.number_input("庫存", min_value=0, step=1, help="輸入庫存數量")
                category = st.text_input("分類", placeholder="輸入分類名稱", help="可選的分類名稱")
                discount = st.number_input("折扣（%）", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", help="輸入折扣百分比")
                description = st.text_area("描述", placeholder="輸入產品描述", help="可選的產品描述")
                response = requests.get(f"{BASE_URL}/supplier/")
                suppliers = handle_response(response)["supplier"] if response.status_code == 200 else []
                supplier_ids = st.multiselect(
                    "供應商",
                    options=[s["id"] for s in suppliers],
                    format_func=lambda x: f"ID: {x} - {next(s['name'] for s in suppliers if s['id'] == x)}",
                    help="選擇相關供應商"
                )
                submit_button = st.form_submit_button("提交")
                if submit_button:
                    with st.spinner("正在新增..."):
                        data = {
                            "name": name,
                            "price": price,
                            "stock": stock,
                            "category": category if category else None,
                            "discount": discount,
                            "description": description if description else None,
                            "supplier_id": supplier_ids
                        }
                        response = requests.post(f"{BASE_URL}/product/", json=data)
                        if handle_response(response):
                            st.success("新增成功！")
                            time.sleep(1)
                            st.rerun()
        
        elif action == "編輯產品":
            with st.form(key="product_edit_form"):
                product_id = st.number_input("產品 ID", min_value=1, step=1, help="輸入要編輯的產品 ID")
                name = st.text_input("名稱", max_chars=100, placeholder="輸入產品名稱", help="名稱需 3-100 字元")
                price = st.number_input("價格", min_value=0.01, step=0.01, format="%.2f", help="輸入產品價格")
                stock = st.number_input("庫存", min_value=0, step=1, help="輸入庫存數量")
                category = st.text_input("分類", placeholder="輸入分類名稱", help="可選的分類名稱")
                discount = st.number_input("折扣（%）", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", help="輸入折扣百分比")
                description = st.text_area("描述", placeholder="輸入產品描述", help="可選的產品描述")
                response = requests.get(f"{BASE_URL}/supplier/")
                suppliers = handle_response(response)["supplier"] if response.status_code == 200 else []
                supplier_ids = st.multiselect(
                    "供應商",
                    options=[s["id"] for s in suppliers],
                    format_func=lambda x: f"ID: {x} - {next(s['name'] for s in suppliers if s['id'] == x)}",
                    help="選擇相關供應商"
                )
                submit_button = st.form_submit_button("提交")
                if submit_button:
                    with st.spinner("正在更新..."):
                        data = {
                            "name": name,
                            "price": price,
                            "stock": stock,
                            "category": category if category else None,
                            "discount": discount,
                            "description": description if description else None,
                            "supplier_id": supplier_ids
                        }
                        response = requests.put(f"{BASE_URL}/product/{product_id}", json=data)
                        if handle_response(response):
                            st.success("更新成功！")
                            time.sleep(1)
                            st.rerun()
        
        elif action == "刪除產品":
            with st.form(key="product_delete_form"):
                product_id = st.number_input("產品 ID", min_value=1, step=1, help="輸入要刪除的產品 ID")
                if st.checkbox("確認刪除此產品？"):
                    submit_button = st.form_submit_button("刪除")
                    if submit_button:
                        with st.spinner("正在刪除..."):
                            response = requests.delete(f"{BASE_URL}/product/{product_id}")
                            if handle_response(response):
                                st.success("刪除成功！")
                                time.sleep(1)
                                st.rerun()

# 供應商管理頁
def supplier_management_page():
    st.title("🏢 供應商管理")
    st.markdown("管理供應商資訊")
    with st.container():
        st.subheader("供應商列表")
        response = requests.get(f"{BASE_URL}/supplier/")
        suppliers = handle_response(response)["supplier"] if response.status_code == 200 else []
        if suppliers:
            df = pd.DataFrame([
                {
                    "ID": s["id"],
                    "名稱": s["name"],
                    "聯絡資訊": s["contact"] or "無",
                    "評分": f"{s['rating']:.1f}" if s["rating"] else "無",
                    "產品數": len(s["product"])
                } for s in suppliers
            ])
            st.dataframe(df, use_container_width=True, height=300)
        
        st.subheader("操作選擇")
        action = st.selectbox("選擇操作", ["查看供應商", "新增供應商", "編輯供應商", "刪除供應商"], help="選擇要執行的操作")
        
        if action == "查看供應商":
            supplier_id = st.number_input("供應商 ID", min_value=1, step=1, help="輸入要查看的供應商 ID")
            if st.button("查詢", use_container_width=True):
                with st.spinner("正在查詢..."):
                    response = requests.get(f"{BASE_URL}/supplier/{supplier_id}")
                    supplier = handle_response(response)
                    if supplier:
                        st.subheader("供應商詳情")
                        st.write(f"**ID**: {supplier['id']}")
                        st.write(f"**名稱**: {supplier['name']}")
                        st.write(f"**聯絡資訊**: {supplier['contact'] or '無'}")
                        st.write(f"**評分**: {supplier['rating'] or '無'}")
                        st.write(f"**產品數**: {len(supplier['product'])}")
        
        elif action == "新增供應商":
            with st.form(key="supplier_create_form"):
                name = st.text_input("名稱", max_chars=100, placeholder="輸入供應商名稱", help="名稱需 1-100 字元")
                contact = st.text_input("聯絡資訊", placeholder="輸入聯絡資訊", help="可選的聯絡資訊")
                rating = st.number_input("評分", min_value=0.0, max_value=5.0, step=0.1, format="%.1f", help="輸入 0-5 的評分")
                submit_button = st.form_submit_button("提交")
                if submit_button:
                    with st.spinner("正在新增..."):
                        data = {
                            "name": name,
                            "contact": contact if contact else None,
                            "rating": rating if rating > 0 else None
                        }
                        response = requests.post(f"{BASE_URL}/supplier/", json=data)
                        if handle_response(response):
                            st.success("新增成功！")
                            time.sleep(1)
                            st.rerun()
        
        elif action == "編輯供應商":
            with st.form(key="supplier_edit_form"):
                supplier_id = st.number_input("供應商 ID", min_value=1, step=1, help="輸入要編輯的供應商 ID")
                name = st.text_input("名稱", max_chars=100, placeholder="輸入供應商名稱", help="名稱需 1-100 字元")
                contact = st.text_input("聯絡資訊", placeholder="輸入聯絡資訊", help="可選的聯絡資訊")
                rating = st.number_input("評分", min_value=0.0, max_value=5.0, step=0.1, format="%.1f", help="輸入 0-5 的評分")
                submit_button = st.form_submit_button("提交")
                if submit_button:
                    with st.spinner("正在更新..."):
                        data = {
                            "name": name,
                            "contact": contact if contact else None,
                            "rating": rating if rating > 0 else None
                        }
                        response = requests.put(f"{BASE_URL}/supplier/{supplier_id}", json=data)
                        if handle_response(response):
                            st.success("更新成功！")
                            time.sleep(1)
                            st.rerun()
        
        elif action == "刪除供應商":
            with st.form(key="supplier_delete_form"):
                supplier_id = st.number_input("供應商 ID", min_value=1, step=1, help="輸入要刪除的供應商 ID")
                if st.checkbox("確認刪除此供應商？"):
                    submit_button = st.form_submit_button("刪除")
                    if submit_button:
                        with st.spinner("正在刪除..."):
                            response = requests.delete(f"{BASE_URL}/supplier/{supplier_id}")
                            if handle_response(response):
                                st.success("刪除成功！")
                                time.sleep(1)
                                st.rerun()

# 歷史記錄頁
def history_page():
    st.title("📜 產品歷史記錄")
    st.markdown("查詢產品的價格和庫存變動歷史")
    with st.container():
        st.subheader("查詢條件")
        with st.form(key="history_form"):
            product_id = st.number_input("產品 ID", min_value=1, step=1, help="輸入要查詢的產品 ID")
            start_date = st.date_input("開始日期", value=None, help="選擇開始日期（可選）")
            end_date = st.date_input("結束日期", value=None, help="選擇結束日期（可選）")
            submit_button = st.form_submit_button("查詢")
            if submit_button:
                with st.spinner("正在查詢..."):
                    params = {
                        "start_date": start_date.isoformat() if start_date else None,
                        "end_date": end_date.isoformat() if end_date else None
                    }
                    response = requests.get(f"{BASE_URL}/product/{product_id}/history", params=params)
                    history = handle_response(response)
                    if history:
                        st.session_state.history = history
                        st.success("查詢成功！")
        
        if "history" in st.session_state and st.session_state.history:
            st.subheader(f"產品 ID: {st.session_state.history[0]['product_id']} - {st.session_state.history[0]['product_name']}")
            df = pd.DataFrame([
                {
                    "時間": pd.to_datetime(h["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "欄位": h["field"],
                    "舊值": f"{h['old_value']:.2f}" if h["old_value"] is not None else "無",
                    "新值": f"{h['new_value']:.2f}" if h["new_value"] is not None else "無",
                    "變動者": h["changed_by"] or "未知"
                } for h in st.session_state.history
            ])
            if not df.empty:
                df["時間"] = pd.to_datetime(df["時間"])
                price_data = df[df["欄位"] == "price"]
                stock_data = df[df["欄位"] == "stock"]
                
                if not price_data.empty:
                    st.subheader("價格變動趨勢")
                    st.line_chart(price_data[["時間", "新值"]].set_index("時間").rename(columns={"新值": "價格"}))
                    st.subheader("價格歷史記錄")
                    st.dataframe(price_data[["時間", "舊值", "新值", "變動者"]], use_container_width=True, height=200)
                
                if not stock_data.empty:
                    st.subheader("庫存變動趨勢")
                    st.line_chart(stock_data[["時間", "新值"]].set_index("時間").rename(columns={"新值": "庫存"}))
                    st.subheader("庫存歷史記錄")
                    st.dataframe(stock_data[["時間", "舊值", "新值", "變動者"]], use_container_width=True, height=200)

# 批量操作頁
def batch_operation_page():
    st.title("🔄 批量操作")
    st.markdown("批量管理多個產品")
    with st.container():
        st.subheader("操作選擇")
        action = st.selectbox("選擇操作", ["批量新增", "批量刪除"], help="選擇要執行的批量操作")
        
        if action == "批量新增":
            with st.form(key="batch_create_form"):
                st.write("輸入多個產品資料（每行一個產品，格式：名稱,價格,庫存,分類,折扣,描述,供應商ID）")
                batch_data = st.text_area("產品資料", placeholder="例：產品A,100.0,50,Electronics,10.0,描述,[1,2]", height=200)
                submit_button = st.form_submit_button("提交")
                if submit_button:
                    with st.spinner("正在批量新增..."):
                        products = []
                        for line in batch_data.split("\n"):
                            if line.strip():
                                try:
                                    name, price, stock, category, discount, description, supplier_ids = line.split(",")
                                    products.append({
                                        "name": name.strip(),
                                        "price": float(price.strip()),
                                        "stock": int(stock.strip()),
                                        "category": category.strip() if category.strip() else None,
                                        "discount": float(discount.strip()),
                                        "description": description.strip() if description.strip() else None,
                                        "supplier_id": [int(s) for s in supplier_ids.strip().strip("[]").split(";") if s]
                                    })
                                except ValueError:
                                    st.error(f"格式錯誤：{line}")
                                    return
                        response = requests.post(f"{BASE_URL}/product/batch_create", json={"product": products})
                        if handle_response(response):
                            st.success("批量新增成功！")
                            time.sleep(1)
                            st.rerun()
        
        elif action == "批量刪除":
            with st.form(key="batch_delete_form"):
                response = requests.get(f"{BASE_URL}/product/")
                products = handle_response(response)["product"] if response.status_code == 200 else []
                selected_ids = st.multiselect(
                    "選擇要刪除的產品",
                    options=[p["id"] for p in products],
                    format_func=lambda x: f"ID: {x} - {next(p['name'] for p in products if p['id'] == x)}",
                    help="選擇要刪除的產品"
                )
                if st.checkbox("確認刪除選中的產品？"):
                    submit_button = st.form_submit_button("刪除")
                    if submit_button:
                        with st.spinner("正在批量刪除..."):
                            response = requests.delete(f"{BASE_URL}/product/batch_delete", json={"ids": selected_ids})
                            if handle_response(response):
                                st.success("批量刪除成功！")
                                time.sleep(1)
                                st.rerun()

# 主邏輯
with st.sidebar:
    st.title("🛒 產品管理系統")
    page = st.selectbox("選擇頁面", ["產品篩選", "產品管理", "供應商管理", "歷史記錄", "批量操作"], help="選擇要操作的功能")

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