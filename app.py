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

@st.cache_data(ttl=60)  # צמצום זמן הזיכרון לדקה אחת בלבד כדי להבטיח רענון נתונים מהיר
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
    
    # המרת מפתחות לטקסט אחיד למניעת בעיות התאמה
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
    st.subheader("🔍 חפשו והוסיפו מוצרים")
    
    col_cat, col_src = st.columns([1, 1])
    with col_cat:
        # הוספנו אימוג'ים ליד כל קטגוריה
        cat_icons = {
            "ירקות טריים": "🥦", "פירות טריים": "🍎", "מוצרי חלב וביצים": "🧀",
            "עוף, בשר, דגים": "🥩", "מאפה ולחם": "🍞", "טואלטיקה וניקוי": "🧼",
            "מזווה": "🥫", "משקאות ואירוח": "🥤", "קפואים": "🧊", "כללי": "🛒"
        }
        category = st.selectbox("בחר מחלקה", sorted(products["category"].unique()), 
                                format_func=lambda x: f"{cat_icons.get(x, '🛒')} {x}")
    with col_src:
        search = st.text_input("חיפוש חופשי").strip()

    if search:
        filtered = products[products["product_name"].str.contains(search, case=False, na=False)]
    else:
        filtered = products[products["category"] == category]

    total_found = len(filtered)
    st.metric(label="מוצרים זמינים", value=total_found)
    
    st.write("---")

    # תצוגת טבלה דחוסה: שם מוצר + צ'קבוקס בצד
    # אנחנו משתמשים ב-container כדי ליצור רשימה נקייה ללא "למטה" מיותר
    for _, product in filtered.head(50).iterrows(): # הגדלנו ל-50 שורות במבט אחד
        product_id = str(product["product_id"])
        
        # יצירת שורה אחת דחוסה: צ'קבוקס (שם המוצר)
        is_checked = st.checkbox(f"{product['product_name']}", 
                                 key=f"check_{product_id}", 
                                 value=product_id in st.session_state.cart)
        
        if is_checked:
            # אם מסומן, הצג תיבת כמות קטנה בצד (בתוך columns כדי שיהיה צמוד)
            c1, c2 = st.columns([4, 1])
            with c2:
                qty = st.number_input("כמות", min_value=1, value=st.session_state.cart.get(product_id, 1), 
                                      step=1, key=f"qty_{product_id}", label_visibility="collapsed")
                st.session_state.cart[product_id] = int(qty)
        elif product_id in st.session_state.cart:
            del st.session_state.cart[product_id]

with tab2:
    st.subheader("📋 מוצרים שנבחרו כרגע")

    if not st.session_state.cart:
        st.info("סל הקניות שלך ריק. חזור לטאב בחירת מוצרים כדי להתחיל.")
    else:
        cart_df = products[products["product_id"].isin(st.session_state.cart.keys())].copy()
        cart_df["quantity"] = cart_df["product_id"].map(st.session_state.cart)

        for cat in sorted(cart_df["category"].unique()):
            with st.expander(f"📦 מחלקת {cat}", expanded=True):
                for _, row in cart_df[cart_df["category"] == cat].iterrows():
                    st.write(f"🍏 **{row['product_name']}** — כמות: `{row['quantity']}`")

with tab3:
    st.subheader("🧠 מנוע אופטימיזציה")
    
    col_budget, col_btn = st.columns([2, 1])
    with col_budget:
        budget = st.number_input("תקציב מקסימלי (אופציונלי, השאר 0 ללא הגבלה)", min_value=0.0, value=0.0, step=10.0)
    with col_btn:
        st.write("<br>", unsafe_allow_html=True)
        calc_button = st.button("🚀 חשב את הסל הזול ביותר", use_container_width=True)

    if calc_button:
        if not st.session_state.cart:
            st.error("הסל ריק! אנא בחר מוצרים.")
        else:
            with st.spinner("משווה מול מחירים חיים..."):
                costs_df = calculate_costs(st.session_state.cart, prices, chains, promotions)
                
                if costs_df.empty:
                    st.error("לא נמצאו מחירים למוצרים אלו ברשתות השיווק.")
                else:
                    best_chain, within_budget = choose_best_chain(costs_df, budget)
                    sorted_costs = costs_df.sort_values("עלות סל")

                    st.write("### 📊 השוואת עלויות מלאה")
                    st.dataframe(sorted_costs[["רשת", "עלות סל"]], use_container_width=True, hide_index=True)

                    st.write("### 🏆 השורה התחתונה")
                    res_col1, res_col2 = st.columns(2)
                    
                    with res_col1:
                        st.markdown(f"""
                        <div class="metric-container">
                            <span style="font-size: 16px; font-weight: bold;">הרשת המשתלמת ביותר</span>
                            <h2 style="color: #8b5cf6;">{best_chain['רשת']}</h2>
                            <span style="font-size: 28px; font-weight: 800;">{best_chain['עלות סל']} ₪</span>
                        </div>
                        """, unsafe_allow_html=True)

                    with res_col2:
                        if len(sorted_costs) > 1:
                            saving = round(sorted_costs.iloc[1]["עלות סל"] - best_chain["עלות סל"], 2)
                            st.markdown(f"""
                            <div class="saving-container">
                                <h2>{saving} ₪</h2>
                                <span>יותר זול מהרשת הבאה בתור!</span>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.info("כאשר נחבר את שאר הרשתות, יוצג כאן מדד החיסכון המדויק!")
