
import streamlit as st
import pandas as pd
from pathlib import Path
import pulp

st.set_page_config(page_title="CartIQ", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.stApp { direction: rtl; text-align: right; }
.main-title { font-size: 42px; font-weight: 800; color: #1b7f3a; margin-bottom: 0; }
.subtitle { font-size: 18px; color: #444; margin-bottom: 25px; }
.result-box { padding: 20px; border-radius: 14px; background-color: #eef9f0; border: 1px solid #b7e4c7; margin-top: 15px; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    return (
        pd.read_csv(DATA_DIR / "products.csv"),
        pd.read_csv(DATA_DIR / "chains.csv"),
        pd.read_csv(DATA_DIR / "prices.csv"),
        pd.read_csv(DATA_DIR / "promotions.csv"),
    )

def get_discount(product_id, chain_id, base_total, promotions):
    promo_rows = promotions[(promotions["product_id"] == product_id) & (promotions["chain_id"] == chain_id)]
    discount = 0.0
    for _, row in promo_rows.iterrows():
        if row["promotion_type"] == "fixed_total":
            discount += float(row["discount_value"])
        elif row["promotion_type"] == "percent":
            discount += base_total * float(row["discount_value"]) / 100
    return discount

def calculate_chain_costs(cart, prices, chains, promotions):
    results = []
    for _, chain in chains.iterrows():
        chain_id = int(chain["chain_id"])
        total = 0.0
        missing = []
        for product_id, quantity in cart.items():
            price_row = prices[(prices["product_id"] == product_id) & (prices["chain_id"] == chain_id)]
            if price_row.empty:
                missing.append(product_id)
                continue
            unit_price = float(price_row.iloc[0]["price"])
            base_total = unit_price * quantity
            discount = get_discount(product_id, chain_id, base_total, promotions)
            total += max(base_total - discount, 0)
        results.append({"chain_id": chain_id, "רשת": chain["chain_name"], "עלות סל": round(total, 2), "מוצרים חסרים": missing})
    return pd.DataFrame(results)

def optimize_best_chain(costs_df, budget):
    model = pulp.LpProblem("CartIQ_Minimize_Shopping_Cart_Cost", pulp.LpMinimize)
    chain_ids = list(costs_df["chain_id"])
    x = pulp.LpVariable.dicts("ChooseChain", chain_ids, lowBound=0, upBound=1, cat="Binary")
    costs = dict(zip(costs_df["chain_id"], costs_df["עלות סל"]))

    model += pulp.lpSum(costs[j] * x[j] for j in chain_ids)
    model += pulp.lpSum(x[j] for j in chain_ids) == 1

    if budget is not None and budget > 0:
        model += pulp.lpSum(costs[j] * x[j] for j in chain_ids) <= budget

    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] == "Optimal":
        selected = next(j for j in chain_ids if pulp.value(x[j]) == 1)
        return costs_df[costs_df["chain_id"] == selected].iloc[0], True

    return costs_df.sort_values("עלות סל").iloc[0], False

products, chains, prices, promotions = load_data()

if "cart" not in st.session_state:
    st.session_state.cart = {}

st.markdown('<p class="main-title">CartIQ 🛒</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">מערכת לאופטימיזציית סל קניות והשוואת מחירים בין רשתות שיווק</p>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["בחירת מוצרים", "רשימת קניות", "תוצאות אופטימיזציה"])

with tab1:
    st.header("בחירת מוצרים לפי קטגוריות")
    categories = sorted(products["category"].unique())
    selected_category = st.selectbox("בחרו קטגוריה", categories)
    search = st.text_input("חיפוש מוצר", placeholder="לדוגמה: חלב, לחם, ביצים")

    if search:
        display_products = products[products["product_name"].str.contains(search, case=False, na=False)]
    else:
        display_products = products[products["category"] == selected_category]

    for _, product in display_products.iterrows():
        product_id = int(product["product_id"])
        col1, col2 = st.columns([3, 1])

        with col1:
            checked = st.checkbox(
                f"{product['product_name']} | {product['brand']} | {product['unit']}",
                value=product_id in st.session_state.cart,
                key=f"check_{product_id}",
            )

        with col2:
            if checked:
                quantity = st.number_input("כמות", min_value=1, value=st.session_state.cart.get(product_id, 1), step=1, key=f"qty_{product_id}")
                st.session_state.cart[product_id] = int(quantity)
            elif product_id in st.session_state.cart:
                del st.session_state.cart[product_id]

    st.subheader("הוספת מוצר ידני")
    manual_product = st.text_input("שם מוצר שאינו מופיע בקטלוג")
    if st.button("הוסף מוצר ידני"):
        if manual_product.strip():
            st.info("בגרסת MVP מוצר ידני יופיע ברשימה, אך לא ייכלל בחישוב המחירים עד לחיבורו למאגר מחירים.")
        else:
            st.warning("יש להזין שם מוצר.")

with tab2:
    st.header("רשימת קניות מסודרת לפי מחלקות")
    if not st.session_state.cart:
        st.warning("עדיין לא נבחרו מוצרים.")
    else:
        cart_products = products[products["product_id"].isin(st.session_state.cart.keys())].copy()
        cart_products["quantity"] = cart_products["product_id"].map(st.session_state.cart)
        for category in sorted(cart_products["category"].unique()):
            st.subheader(category)
            for _, row in cart_products[cart_products["category"] == category].iterrows():
                st.write(f"• {row['product_name']} — כמות: {row['quantity']}")

with tab3:
    st.header("חישוב סל הקניות המשתלם ביותר")
    budget = st.number_input("תקציב מקסימלי לסל הקניות", min_value=0.0, value=0.0, step=10.0)

    if st.button("חשב סל אופטימלי"):
        if not st.session_state.cart:
            st.error("יש לבחור לפחות מוצר אחד לפני ביצוע החישוב.")
        else:
            costs_df = calculate_chain_costs(st.session_state.cart, prices, chains, promotions)
            best_chain, is_within_budget = optimize_best_chain(costs_df, budget if budget > 0 else None)

            st.subheader("השוואת עלויות בין רשתות")
            sorted_costs = costs_df[["רשת", "עלות סל"]].sort_values("עלות סל")
            st.dataframe(sorted_costs, use_container_width=True)

            st.markdown('<div class="result-box">', unsafe_allow_html=True)
            st.success(f"הרשת המשתלמת ביותר: {best_chain['רשת']}")
            st.metric("עלות הסל", f"{best_chain['עלות סל']} ₪")

            if budget > 0 and not is_within_budget:
                st.warning("לא נמצאה רשת שעומדת בתקציב שהוגדר. מוצגת הרשת הזולה ביותר, אך קיימת חריגה מהתקציב.")

            if len(sorted_costs) > 1:
                saving = round(sorted_costs.iloc[1]["עלות סל"] - best_chain["עלות סל"], 2)
                st.metric("חיסכון מול הרשת הבאה", f"{saving} ₪")

            st.markdown('</div>', unsafe_allow_html=True)
