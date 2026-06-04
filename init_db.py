import pandas as pd
from pathlib import Path
from database import get_connection, create_tables

DATA_DIR = Path("data")

def load_csv_to_db():
    # 1. יצירת הטבלאות עם כל החוקים והמפתחות (Primary Keys)
    create_tables()
    conn = get_connection()
    cursor = conn.cursor()

    # 2. ריקון הטבלאות למקרה שיש בהן כבר נתונים, כדי למנוע כפילויות
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM chains")
    cursor.execute("DELETE FROM prices")
    cursor.execute("DELETE FROM promotions")
    conn.commit()

    # 3. הכנסת הנתונים מקבצי ה-CSV במצב 'append' 
    # זה מוסיף את הנתונים מבלי לדרוס ולמחוק את הגדרות הטבלה!
    
    try:
        pd.read_csv(DATA_DIR / "products.csv").to_sql(
            "products", conn, if_exists="append", index=False
        )
        pd.read_csv(DATA_DIR / "chains.csv").to_sql(
            "chains", conn, if_exists="append", index=False
        )
        pd.read_csv(DATA_DIR / "prices.csv").to_sql(
            "prices", conn, if_exists="append", index=False
        )
        pd.read_csv(DATA_DIR / "promotions.csv").to_sql(
            "promotions", conn, if_exists="append", index=False
        )
        print("Database initialized successfully with constraints preserved.")
    except Exception as e:
        print(f"Error loading CSVs: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    load_csv_to_db()
