import pandas as pd
from pathlib import Path
from database import get_connection, create_tables

DATA_DIR = Path("data")

def load_csv_to_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. הפעולה הקריטית: מחיקה מוחלטת של הטבלאות הפגומות מהזיכרון
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS chains")
    cursor.execute("DROP TABLE IF EXISTS prices")
    cursor.execute("DROP TABLE IF EXISTS promotions")
    conn.commit()

    # 2. בניית הטבלאות מחדש, והפעם כשהן ריקות - המפתחות הראשיים ייווצרו בהצלחה!
    create_tables()

    # 3. הכנסת הנתונים הבסיסיים מקבצי ה-CSV
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
