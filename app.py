import streamlit as st
import pandas as pd
from pathlib import Path
import sqlite3
import pulp

# הגדרת תצורת עמוד ראשונית
st.set_page_config(page_title="CartIQ | סל קניות חכם", page_icon="🛒", layout="wide")

# הזרקת CSS מתקדמת לשדרוג חזותי מלא ותמיכה ב-RTL
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700&family=Heebo:wght@500;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Assistant', sans-serif;
        direction: rtl;
        text-align: right;
        background-color: #f8fafc;
    }
    
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        direction: rtl;
        text-align: right;
        font-family: 'Heebo', sans-serif;
    }

    .hero-banner {
        background: linear-gradient(135deg, #166534 0%, #22c55e 100%);
        padding: 50px 40px;
        border-radius: 24px;
        color: white;
        text-align: center;
        margin-bottom: 35px;
        box-shadow: 0 15px 35px rgba(34, 197, 94, 0.2);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .cartiq-logo {
        width: 90px;
        height: 90px;
        margin-bottom: 15px;
    }
    
    .cartiq-logo svg {
        width: 100%;
        height: 100%;
    }
    
    .cartiq-logo .cart-body { fill: #ffffff; }
    .cartiq-logo .cart-wheels { fill: #fed7aa; }
    .cartiq-logo .cart-light { fill: #f97316; }

    .hero-title {
        font-size: 55px;
        font-weight: 800;
        margin: 0;
        letter-spacing: -2px;
        color: #ffffff;
    }
    .hero-subtitle {
        font-size: 22px;
        opacity: 0.95;
        margin-top: 8px;
        font-weight: 300;
        color: #e2e8f0;
    }

    .product-card {
        background-color: #ffffff;
        border-right: 6px solid #22c55e;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
        margin-top: 15px;
    }

    .metric-container {
        background-color: white;
        border-radius: 16px;
        padding: 25px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.03);
        border-top: 5px solid #8b5cf6;
        text-align: center;
        margin-bottom: 20px;
    }
    
    .saving-container {
        background: linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%);
        border: 1px solid #f97316;
        border-radius: 16px;
        padding: 25px;
        text-align: center;
        color: #c2410c;
        margin-bottom: 20px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 8px 8px 0px 0px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #22c55e !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("data")

@st.cache_data(ttl=600)  # שמירה בזיכרון ל-10 דקות כדי לשמור על מהירות שיא
def load_data():
    db_path = DATA_DIR / "cartiq.db"
    if not db_path.exists():
        st.error("מסד הנתונים לא נמצא במערכת! ודא שהאוטומציה רצה בהצלחה.")
        st.stop()
        
    conn = sqlite3.connect(db_path)
    products = pd.read_sql_query("SELECT * FROM products", conn)
    chains = pd.read_sql_query("SELECT * FROM chains", conn)
    prices = pd.read_sql_query("SELECT * FROM prices", conn)
    promotions = pd.read_sql_query("SELECT * FROM promotions", conn)
    conn.close()
    
    # המרת מפתחות למספרים שלמים כדי למנוע בעיות התאמה בטעינה
    products["product_id"] = products["product_id"].astype(str)
    prices["product_id"] = prices["product_id"].astype(str)
    prices["chain_id"] = prices["chain_id"].astype(int)
    chains["chain_id"] = chains["chain_id"].astype(int)
    
    return products, chains, prices, promotions

def get_discount(product_id, chain_id, base_total, promotions):
    if promotions.empty:
        return 0
    rows = promotions[(promotions["product_id"] == product_id) & (promotions["chain_id"] == chain_id)]
    discount = 0
    for _, row in rows.iterrows():
        if row["promotion_type"] == "fixed_total":
            discount += float(row["discount_value"])
        elif row["promotion_type"] == "percent":
            discount += base_total * float(row["discount_value"]) / 100
    return discount

def calculate_costs(cart, prices, chains, promotions):
    results = []
    for _, chain in chains.iterrows():
        chain_id = int(chain["chain_id"])
        chain_name = chain["chain_name"]
        total = 0
        has_items = False

        for product_id, quantity in cart.items():
            price_row = prices[(prices["product_id"] == product_id) & (prices["chain_id"] == chain_id)]
            if price_row.empty:
                continue

            has_items = True
            unit_price = float(price_row.iloc[0]["price"])
            base_total = unit_price * quantity
            discount = get_discount(product_id, chain_id, base_total, promotions)
            total += max(base_total - discount, 0)

        if has_items:
            results.append({
                "chain_id": chain_id,
                "רשת": chain_name,
                "עלות סל": round(total, 2)
            })
            
    return pd.DataFrame(results) if results else pd.DataFrame(columns=["chain_id", "רשת", "עלות סל"])

def choose_best_chain(costs_df, budget):
    if costs_df.empty:
        return None, False
        
    model = pulp.LpProblem("CartIQ_Minimize_Cost", pulp.LpMinimize)
    chain_ids = list(costs_df["chain_id"])
    costs = dict(zip(costs_df["chain_id"], costs_df["עלות סל"]))

    x = pulp.LpVariable.dicts("ChooseChain", chain_ids, lowBound=0, upBound=1, cat="Binary")
    model += pulp.lpSum(costs[j] * x[j] for j in chain_ids)
    model += pulp.lpSum(x[j] for j in chain_ids) == 1

    if budget > 0:
        model += pulp.lpSum(costs[j] * x[j] for j in chain_ids) <= budget

    status = model.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[status] == "Optimal":
        selected_id = next(j for j in chain_ids if pulp.value(x[j]) == 1)
        return costs_df[costs_df["chain_id"] == selected_id].iloc[0], True

    return costs_df.sort_values("עלות סל").iloc[0], False

# טעינת נתונים חיה ממסד הנתונים
products, chains, prices, promotions = load_data()

if "cart" not in st.session_state:
    st.session_state.cart = {}

# באנר פתיחה ממותג
st.markdown("""
<div class="hero-banner">
    <div class="cartiq-logo">
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <path class="cart-body" d="M10,20 L25,20 L35,65 L85,65 L90,30 L30,30" stroke-width="5" stroke="white" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            <circle class="cart-wheels" cx="40" cy="80" r="8" fill="white"/>
            <circle class="cart-wheels" cx="80" cy="80" r="8" fill="white"/>
            <path class="cart-light" d="M50,15 L50,15 A12,12 0 0 1 62,27 L62,35 L38,35 L38,27 A12,12 0 0 1 50,15 L50,15" stroke-width="3" stroke="#f97316" fill="white"/>
            <rect class="cart-light" x="42" y="35" width="16" height="5" rx="2" fill="#f97316"/>
        </svg>
    </div>
    <div class="hero-title">CartIQ</div>
    <div class="hero-subtitle">הסל החכם שלך: השוואה ואופטימיזציה בזמן אמת מול מחירי אמת</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "🛍️ מרכז בחירת מוצרים",
    "📋 רשימת הקניות שלי",
    "📊 אופטימיזציה ותוצאות"
])

with tab1:
    st.subheader("🔍 חפשו והוסיפו מוצרים מסניפי השטח")
    
    col_cat, col_src = st.columns([1, 1])
    with col_cat:
        category = st.selectbox("בחר מחלקה / קטגוריה", sorted(products["category"].unique()))
    with col_src:
        search = st.text_input("חיפוש חופשי (מומלץ! הקלידו שם מוצר או מותג)")

 # מנגנון סינון חכם
    if search:
        filtered = products[products["product_name"].str.contains(search, case=False, na=False)]
    else:
        filtered = products[products["category"] == category]
