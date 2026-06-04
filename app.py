import streamlit as st
import pandas as pd
from pathlib import Path
import pulp

st.set_page_config(page_title="CartIQ", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.stApp {
    direction: rtl;
    text-align: right;
}
h1, h2, h3, p, label, div {
    direction: rtl;
    text-align: right;
}
.title {
    font-size: 44px;
    font-weight: 800;
    color: #1b7f3a;
}
.subtitle {
    font-size: 18px;
    color: #555;
}
.result-box {
    background-color: #eef9f0;
    border: 1px solid #b7e4c7;
    padding: 20px;
    border-radius: 14px;
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


products, chains, prices, promotions = load_data()

if "cart" not in st.session_state:
    st.session_state.cart = {}

st.markdown('<div class="title">CartIQ 🛒</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">מערכת לאופטימיזציית סל קניות והשוואת מחירים בין רשתות שיווק</div>',
    unsafe_allow_html=True
)

st.divider()

tab1, tab2, tab3 = st.tabs([
    "🛍️ בחירת מוצרים",
    "📋 רשימת קניות",
    "📊 תוצאות אופטימיזציה"
])

with tab1:
    st.header("בחירת מוצרים לפי קטגוריות")

    category = st.selectbox("בחרו קטגוריה", sorted(products["category"].unique()))
    search = st.text_input("חיפוש מוצר")

    if search:
        filtered = products[
            products["product_name"].str.contains(search, case=False, na=False)
        ]
    else:
        filtered = products[products["category"] == category]

    for _, product in filtered.iterrows():
        product_id = int(product["product_id"])

        col1, col2 = st.columns([3, 1])

        with col1:
            checked = st.checkbox(
                f"{product['product_name']} | {product['brand']} | {product['unit']}",
                value=product_id in st.session_state.cart,
                key=f"check_{product_id}"
            )

        with col2:
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
    st.header("רשימת קניות מסודרת לפי מחלקות")

    if not st.session_state.cart:
        st.warning("עדיין לא נבחרו מוצרים.")
    else:
        cart_df = products[
            products["product_id"].isin(st.session_state.cart.keys())
        ].copy()

        cart_df["quantity"] = cart_df["product_id"].map(st.session_state.cart)

        for category in sorted(cart_df["category"].unique()):
            st.subheader(category)
            for _, row in cart_df[cart_df["category"] == category].iterrows():
                st.write(f"• {row['product_name']} — כמות: {row['quantity']}")

with tab3:
    st.header("חישוב סל הקניות המשתלם ביותר")

    budget = st.number_input(
        "תקציב מקסימלי לסל הקניות",
        min_value=0.0,
        value=0.0,
        step=10.0
    )

    if st.button("חשב סל אופטימלי"):
        if not st.session_state.cart:
            st.error("יש לבחור לפחות מוצר אחד לפני ביצוע החישוב.")
        else:
            with st.spinner("משווים מחירים בין רשתות השיווק..."):
                costs_df = calculate_costs(
                    st.session_state.cart,
                    prices,
                    chains,
                    promotions
                )

                best_chain, within_budget = choose_best_chain(costs_df, budget)

            st.subheader("השוואת עלויות בין רשתות")
            sorted_costs = costs_df.sort_values("עלות סל")
            st.dataframe(sorted_costs[["רשת", "עלות סל"]], use_container_width=True)

            st.markdown('<div class="result-box">', unsafe_allow_html=True)

            st.success(f"הרשת המשתלמת ביותר היא: {best_chain['רשת']}")
            st.metric("עלות הסל", f"{best_chain['עלות סל']} ₪")

            if budget > 0 and not within_budget:
                st.warning("לא נמצאה רשת שעומדת בתקציב שהוגדר. מוצגת הרשת הזולה ביותר, אך קיימת חריגה מהתקציב.")

            if len(sorted_costs) > 1:
                saving = round(
                    sorted_costs.iloc[1]["עלות סל"] - best_chain["עלות סל"],
                    2
                )
                st.metric("חיסכון מול הרשת הבאה", f"{saving} ₪")

            st.markdown('</div>', unsafe_allow_html=True)
            
