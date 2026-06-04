import streamlit as st
import pandas as pd
from pathlib import Path
import sqlite3
import pulp

# הגדרת תצורת עמוד ראשונית
st.set_page_config(page_title="CartIQ | סל קניות חכם", page_icon="🛒", layout="wide")

# CSS - עיצוב ה-RTL
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"] { direction: rtl; text-align: right; background-color: #f8fafc; font-family: 'Assistant', sans-serif; }
    .hero-banner { background: linear-gradient(135deg, #166534 0%, #22c55e 100%); padding: 30px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .hero-title { font-size: 40px; font-weight: 800; margin: 0; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("data")

@st.cache_data(ttl=60)
def load_data():
    db_path = DATA_DIR / "cartiq.db"
    conn = sqlite3.connect(db_path)
    products = pd.read_sql_query("SELECT * FROM products", conn)
    chains = pd.read_sql_query("SELECT * FROM chains", conn)
    prices = pd.read_sql_query("SELECT * FROM prices", conn)
    promotions = pd.read_sql_query("SELECT * FROM promotions", conn)
    conn.close()
    products["product_id"] = products["product_id"].astype(str)
    prices["product_id"] = prices["product_id"].astype(str)
    return products, chains, prices, promotions

def calculate_costs(cart, prices, chains, promotions):
    results = []
    for _, chain in chains.iterrows():
        total = 0
        for pid, qty in cart.items():
            row = prices[(prices["product_id"] == pid) & (prices["chain_id"] == chain["chain_id"])]
            if not row.empty: total += float(row.iloc[0]["price"]) * qty
        if total > 0: results.append({"רשת": chain["chain_name"], "עלות סל": round(total, 2)})
    return pd.DataFrame(results)

products, chains, prices, promotions = load_data()
if "cart" not in st.session_state: st.session_state.cart = {}

st.markdown('<div class="hero-banner"><div class="hero-title">CartIQ</div></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🛍️ מוצרים", "📋 סל", "📊 אופטימיזציה"])

with tab1:
    col_cat, col_src = st.columns([1, 1])
    cat_list = sorted(products["category"].unique())
    category = col_cat.selectbox("בחר מחלקה", cat_list)
    search = col_src.text_input("חיפוש חופשי").strip()

    filtered = products[products["product_name"].str.contains(search, case=False, na=False)] if search else products[products["category"] == category]

    for _, product in filtered.head(50).iterrows():
        pid = str(product["product_id"])
        c1, c2, c3 = st.columns([0.2, 3.0, 0.8])
        is_checked = c1.checkbox("", key=f"check_{pid}", value=pid in st.session_state.cart)
        c2.markdown(f"<p style='margin: 0; padding-top: 5px;'>{product['product_name']}</p>", unsafe_allow_html=True)
        if is_checked:
            st.session_state.cart[pid] = int(c3.number_input("כ", min_value=1, value=st.session_state.cart.get(pid, 1), step=1, key=f"qty_{pid}", label_visibility="collapsed"))
        elif pid in st.session_state.cart:
            del st.session_state.cart[pid]

with tab2:
    if not st.session_state.cart: st.info("הסל ריק")
    else:
        for pid, qty in st.session_state.cart.items():
            name = products.loc[products["product_id"] == pid, "product_name"].values[0]
            st.write(f"✅ {name} - כמות: {qty}")

with tab3:
    budget = st.number_input("תקציב (₪)", min_value=0.0, value=0.0)
    if st.button("🚀 חשב"):
        costs = calculate_costs(st.session_state.cart, prices, chains, promotions)
        if not costs.empty:
            avg_cost = costs["עלות סל"].mean()
            st.metric("עלות סל ממוצעת", f"{avg_cost:.2f} ₪")
            if budget > 0 and avg_cost > budget:
                st.error(f"חריגה בתקציב: {avg_cost - budget:.2f} ₪")
