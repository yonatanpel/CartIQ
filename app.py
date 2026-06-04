import streamlit as st
import pandas as pd
from pathlib import Path
import pulp

# הגדרת תצורת עמוד ראשונית
st.set_page_config(page_title="CartIQ | סל קניות חכם", page_icon="🛒", layout="wide")

# הזרקת CSS מתקדמת לשדרוג חזותי מלא وتמיכה ב-RTL
st.markdown("""
<style>
    /* טעינת גופנים מבית גוגל */
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700&family=Heebo:wght@500;800&display=swap');
    
    /* הגדרות בסיסיות לכל האפליקציה */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Assistant', sans-serif;
        direction: rtl;
        text-align: right;
        background-color: #f8fafc;
    }
    
    /* התאמת כותרות רשמיות של סטרים-ליט */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        direction: rtl;
        text-align: right;
        font-family: 'Heebo', sans-serif;
    }

    /* באנר הירוק הראשי בכניסה לאתר */
    .hero-banner {
        background: linear-gradient(135deg, #166534 0%, #22c55e 100%);
        padding: 60px 40px;
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

    /* עיצוב הלוגו בתוך הבאנר */
    .cartiq-logo {
        width: 100px;
        height: 100px;
        margin-bottom: 20px;
    }
    
    .cartiq-logo svg {
        width: 100%;
        height: 100%;
        fill: white; /* צבע ברירת מחדל */
    }
    
    .cartiq-logo .cart-body { fill: #ffffff; }
    .cartiq-logo .cart-wheels { fill: #fed7aa; } /* כתום בהיר לגלגלים */
    .cartiq-logo .cart-light { fill: #f97316; }   /* כתום מלא לאור */

    .hero-title {
        font-size: 64px;
        font-weight: 800;
        margin: 0;
        letter-spacing: -2px;
        font-family: 'Heebo', sans-serif;
        color: #ffffff;
    }
    .hero-subtitle {
        font-size: 24px;
        opacity: 0.95;
        margin-top: 10px;
        font-weight: 300;
        color: #e2e8f0;
    }

    /* עיצוב כרטיסי מוצרים בטאב הבחירה */
    .product-card {
        background-color: #ffffff;
        border-right: 6px solid #22c55e;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
        margin-bottom: 12px;
        transition: transform 0.2s;
    }
    .product-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.05);
    }

    /* קופסאות תוצאה מעוצבות (דאשבורד סיכום) */
    .metric-container {
        background-color: white;
        border-radius: 16px;
        padding: 25px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.03);
        border-top: 5px solid #8b5cf6; /* סגול טכנולוגי לאופטימיזציה */
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

    /* עיצוב טאבים מותאם אישית */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
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

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    products = pd.read_csv(DATA_DIR / "products.csv")
    chains = pd.read_csv(DATA_DIR / "chains.csv")
    prices = pd.read_csv(DATA_DIR / "prices.csv")
    promotions = pd.read_csv(DATA_DIR / "promotions.csv")
    return products, chains, prices, promotions

def get_discount(product_id, chain_id, base_total, promotions):
    rows = promotions[
        (promotions["product_id"] == product_id) &
        (promotions["chain_id"] == chain_id)
    ]
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

        for product_id, quantity in cart.items():
            price_row = prices[
                (prices["product_id"] == product_id) &
                (prices["chain_id"] == chain_id)
            ]
            if price_row.empty:
                continue

            unit_price = float(price_row.iloc[0]["price"])
            base_total = unit_price * quantity
            discount = get_discount(product_id, chain_id, base_total, promotions)
            total += max(base_total - discount, 0)

        results.append({
            "chain_id": chain_id,
            "רשת": chain_name,
            "עלות סל": round(total, 2)
        })
    return pd.DataFrame(results)

def choose_best_chain(costs_df, budget):
    model = pulp.LpProblem("CartIQ_Minimize_Cost", pulp.LpMinimize)
    chain_ids = list(costs_df["chain_id"])
    costs = dict(zip(costs_df["chain_id"], costs_df["עלות סל"]))

    x = pulp.LpVariable.dicts(
        "ChooseChain",
        chain_ids,
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    model += pulp.lpSum(costs[j] * x[j] for j in chain_ids)
    model += pulp.lpSum(x[j] for j in chain_ids) == 1

    if budget > 0:
        model += pulp.lpSum(costs[j] * x[j] for j in chain_ids) <= budget

    status = model.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[status] == "Optimal":
        selected_id = next(j for j in chain_ids if pulp.value(x[j]) == 1)
        return costs_df[costs_df["chain_id"] == selected_id].iloc[0], True

    return costs_df.sort_values("עלות סל").iloc[0], False

# טעינת נתונים
try:
    products, chains, prices, promotions = load_data()
except Exception as e:
    st.error("שגיאה בטעינת קבצי ה-CSV. ודא שתיקיית data קיימת ומכילה את הקבצים הנכונים.")
    st.stop()

if "cart" not in st.session_state:
    st.session_state.cart = {}

# באנר פתיחה מעוצב הכולל לוגו SVG ושם המערכת
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
    <div class="hero-subtitle">הסל החכם שלך: השוואה ואופטימיזציה בין רשתות השיווק</div>
</div>
""", unsafe_allow_html=True)

# יצירת הטאבים עם אייקונים משופרים
tab1, tab2, tab3 = st.tabs([
    "🛍️ מרכז בחירת מוצרים",
    "📋 רשימת הקניות שלי",
    "📊 אופטימיזציה ותוצאות"
])

with tab1:
    st.subheader("🔍 חפשו והוסיפו מוצרים לסל")
    
    col_cat, col_src = st.columns([1, 1])
    with col_cat:
        category = st.selectbox("בחר מחלקה / קטגוריה", sorted(products["category"].unique()))
    with col_src:
        search = st.text_input("חיפוש חופשי (לפי שם מוצר)")

    if search:
        filtered = products[products["product_name"].str.contains(search, case=False, na=False)]
    else:
        filtered = products[products["category"] == category]

    st.write("---")

    # הצגת המוצרים בעיצוב כרטיסים נקי
    for _, product in filtered.iterrows():
        product_id = int(product["product_id"])
        
        st.markdown(f"""
        <div class="product-card">
            <strong>{product['product_name']}</strong> | מותג: {product['brand']} | יחידה: {product['unit']}
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, _ = st.columns([2, 2, 5])
        with c1:
            checked = st.checkbox(
                "הוסף לסל", 
                value=product_id in st.session_state.cart, 
                key=f"check_{product_id}"
            )
        with c2:
            if checked:
                quantity = st.number_input(
                    "כמות",
                    min_value=1,
                    value=st.session_state.cart.get(product_id, 1),
                    step=1,
                    key=f"qty_{product_id}"
                )
                st.session_state.cart[product_id] = int(quantity)
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
        budget = st.number_input(
            "הגדר תקציב מקסימלי (אופציונלי, השאר 0 ללא הגבלה)",
            min_value=0.0,
            value=0.0,
            step=10.0
        )
    with col_btn:
        st.write("<br>", unsafe_allow_html=True) 
        calc_button = st.button("🚀 חשב את הסל הזול ביותר", use_container_width=True)

    if calc_button:
        if not st.session_state.cart:
            st.error("הסל ריק! אנא בחר לפחות מוצר אחד בטאב הראשון.")
        else:
            with st.spinner("מריץ אלגוריתם השוואה ומחפש הנחות ומבצעים..."):
                costs_df = calculate_costs(st.session_state.cart, prices, chains, promotions)
                best_chain, within_budget = choose_best_chain(costs_df, budget)
                sorted_costs = costs_df.sort_values("עלות סל")

            st.write("### 📊 השוואת עלויות מלאה")
            st.dataframe(sorted_costs[["רשת", "עלות סל"]], use_container_width=True, hide_index=True)

            st.write("### 🏆 השורה התחתונה")
            
            res_col1, res_col2 = st.columns(2)
            
            with res_col1:
                st.markdown(f"""
                <div class="metric-container">
                    <span style="font-size: 16px; color: #64748b; font-weight: bold;">הרשת המשתלמת ביותר</span>
                    <h2 style="color: #8b5cf6; margin: 5px 0; font-family: 'Heebo', sans-serif;">{best_chain['רשת']}</h2>
                    <span style="font-size: 28px; font-weight: 800; color: #1e293b;">{best_chain['עלות סל']} ₪</span>
                </div>
                """, unsafe_allow_html=True)

            with res_col2:
                if len(sorted_costs) > 1:
                    saving = round(sorted_costs.iloc[1]["עלות סל"] - best_chain["עלות סל"], 2)
                    st.markdown(f"""
                    <div class="saving-container">
                        <span style="font-size: 16px; font-weight: bold;">החיסכון שלך ברשת זו</span>
                        <h2 style="margin: 5px 0; font-weight: 800; font-family: 'Heebo', sans-serif;">{saving} ₪</h2>
                        <span style="font-size: 14px;">יותר זול מהרשת הבאה בתור!</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("אין מספיק נתונים ברשתות אחרות כדי לחשב יחס חיסכון.")

            if budget > 0 and not within_budget:
                st.warning("⚠️ שימו לב: לא נמצאה רשת שעומדת במגבלת התקציב שהגדרתם. מוצגת הרשת הזולה ביותר הזמינה.")
