import pandas as pd
from pathlib import Path
from database import get_connection, create_tables
from fetch_prices import determine_category

DATA_DIR = Path("data")

def load_csv_to_db():
    conn = get_connection()
    cursor = conn.cursor()

    # מחיקה מלאה של הטבלאות הישנות לאיפוס מוחלט
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS chains")
    cursor.execute("DROP TABLE IF EXISTS prices")
    cursor.execute("DROP TABLE IF EXISTS promotions")
    conn.commit()

    # הקמה נקייה מחדש
    create_tables()

    try:
        # טעינת ה-CSV של המוצרים
        df_products = pd.read_csv(DATA_DIR / "products.csv")
        
        # הקסם קורה פה: אנחנו דורסים את הקטגוריות הישנות מה-CSV ומסווגים אותן מחדש לפי החוקים החדשים!
        if "product_name" in df_products.columns:
            df_products["category"] = df_products["product_name"].apply(determine_category)

        # שמירה לטבלה
        df_products.to_sql("products", conn, if_exists="append", index=False)
        
        # טעינת שאר קבצי הבסיס
        pd.read_csv(DATA_DIR / "chains.csv").to_sql("chains", conn, if_exists="append", index=False)
        pd.read_csv(DATA_DIR / "prices.csv").to_sql("prices", conn, if_exists="append", index=False)
        pd.read_csv(DATA_DIR / "promotions.csv").to_sql("promotions", conn, if_exists="append", index=False)
        
        print("Database initialized successfully with perfectly unified categories!")
    except Exception as e:
        print(f"Error loading CSVs: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    load_csv_to_db()
