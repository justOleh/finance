"""
frontend.app
------------
Streamlit web UI for the My Finance expense tracker.

Pages (sidebar navigation)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dashboard
    Summary metrics (total count, total spent, average), a bar chart of
    spending by store/merchant, and a filterable table of all expenses.
    Date-range and store filters are available in the sidebar.

Add Expense
    Manual expense entry form.  Supports a dynamic list of line items
    (name + price per item).  Submits to ``POST /expenses`` on the backend.

Upload Receipt
    Upload a JPEG/PNG receipt photo.  The image is sent to
    ``POST /receipts/upload`` on the backend which proxies it to the Receipt
    Parser service and auto-creates an expense record from the parsed data.

Environment variables
~~~~~~~~~~~~~~~~~~~~~
BACKEND_URL  Base URL of the backend API.  Default: ``http://localhost:8000``
"""

import os
from datetime import date, timedelta
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="💰 My Finance Tracker", page_icon="💰", layout="wide")
st.title("💰 My Finance Tracker")

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
page = st.sidebar.radio("Navigation", ["Dashboard", "Add Expense", "Upload Receipt"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_expenses(start_date=None, end_date=None, store=None) -> list[dict]:
    params = {}
    if start_date:
        params["start_date"] = str(start_date)
    if end_date:
        params["end_date"] = str(end_date)
    if store:
        params["store"] = store
    try:
        resp = httpx.get(f"{BACKEND_URL}/expenses/", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Failed to fetch expenses: {exc}")
        return []


def post_expense(payload: dict) -> dict | None:
    try:
        resp = httpx.post(f"{BACKEND_URL}/expenses/", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Failed to create expense: {exc}")
        return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
if page == "Dashboard":
    st.header("📊 Dashboard")

    st.sidebar.subheader("Filters")
    start_filter = st.sidebar.date_input("Start date", value=date.today() - timedelta(days=30))
    end_filter = st.sidebar.date_input("End date", value=date.today())
    store_filter = st.sidebar.text_input("Store (contains)")

    expenses = fetch_expenses(
        start_date=start_filter,
        end_date=end_filter,
        store=store_filter if store_filter else None,
    )

    if expenses:
        df = pd.DataFrame(expenses)
        total_amount = df["total"].sum()
        avg_amount = df["total"].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Expenses", len(expenses))
        col2.metric("Total Spent", f"${total_amount:,.2f}")
        col3.metric("Average Expense", f"${avg_amount:,.2f}")

        st.subheader("Spending by Store")
        by_store = df.groupby("store")["total"].sum().reset_index()
        fig = px.bar(by_store, x="store", y="total", labels={"total": "Amount ($)", "store": "Store"})
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("All Expenses")
        display_df = df[["date", "store", "total", "notes"]].copy()
        display_df["items"] = df["items"].apply(
            lambda x: ", ".join(f"{i.get('name','')} (${i.get('price',0):.2f})" for i in x) if x else ""
        )
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No expenses found for the selected filters.")

# ---------------------------------------------------------------------------
# Add Expense
# ---------------------------------------------------------------------------
elif page == "Add Expense":
    st.header("➕ Add Expense")

    if "items_list" not in st.session_state:
        st.session_state.items_list = [{"name": "", "price": 0.0}]

    with st.form("add_expense_form"):
        expense_date = st.date_input("Date", value=date.today())
        store = st.text_input("Store / Merchant")
        total = st.number_input("Total ($)", min_value=0.0, step=0.01, format="%.2f")
        notes = st.text_area("Notes (optional)")

        st.subheader("Items")
        updated_items = []
        for idx, item in enumerate(st.session_state.items_list):
            c1, c2 = st.columns([3, 1])
            name = c1.text_input(f"Item {idx + 1} name", value=item["name"], key=f"item_name_{idx}")
            price = c2.number_input(f"Price", value=float(item["price"]), min_value=0.0, step=0.01, format="%.2f", key=f"item_price_{idx}")
            updated_items.append({"name": name, "price": price})

        col_add, col_sub = st.columns(2)
        add_item = col_add.form_submit_button("+ Add Item")
        remove_item = col_sub.form_submit_button("- Remove Last Item")
        submitted = st.form_submit_button("💾 Save Expense")

    if add_item:
        st.session_state.items_list.append({"name": "", "price": 0.0})
        st.rerun()

    if remove_item and len(st.session_state.items_list) > 1:
        st.session_state.items_list.pop()
        st.rerun()

    if submitted:
        if not store:
            st.error("Store name is required.")
        else:
            payload = {
                "date": str(expense_date),
                "store": store,
                "total": total,
                "notes": notes or None,
                "items": [i for i in updated_items if i["name"]],
            }
            result = post_expense(payload)
            if result:
                st.success(f"✅ Expense saved! ID: {result['id']}")
                st.session_state.items_list = [{"name": "", "price": 0.0}]
                st.rerun()

# ---------------------------------------------------------------------------
# Upload Receipt
# ---------------------------------------------------------------------------
elif page == "Upload Receipt":
    st.header("📷 Upload Receipt")

    uploaded_file = st.file_uploader("Choose a receipt image", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        st.image(uploaded_file, caption="Receipt Preview", use_column_width=True)

        if st.button("🔍 Parse & Save Receipt"):
            with st.spinner("Uploading and parsing receipt..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    resp = httpx.post(f"{BACKEND_URL}/receipts/upload", files=files, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()

                    st.success("✅ Receipt uploaded and parsed successfully!")
                    st.subheader("Extracted Data")
                    col1, col2 = st.columns(2)
                    col1.metric("Store", data.get("store", "N/A"))
                    col2.metric("Total", f"${data.get('total', 0):.2f}")
                    st.write(f"**Date:** {data.get('date', 'N/A')}")

                    if data.get("items"):
                        st.subheader("Items")
                        items_df = pd.DataFrame(data["items"])
                        st.dataframe(items_df, use_container_width=True)

                    if data.get("notes"):
                        with st.expander("Raw OCR Text"):
                            st.text(data["notes"])

                except Exception as exc:
                    st.error(f"Failed to process receipt: {exc}")
