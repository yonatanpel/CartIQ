import pandas as pd
from pathlib import Path
from database import get_connection, create_tables

DATA_DIR = Path("data")

def load_csv_to_db():
    create_tables()
    conn = get_connection()

    pd.read_csv(DATA_DIR / "products.csv").to_sql(
        "products", conn, if_exists="replace", index=False
    )

    pd.read_csv(DATA_DIR / "chains.csv").to_sql(
        "chains", conn, if_exists="replace", index=False
    )

    pd.read_csv(DATA_DIR / "prices.csv").to_sql(
        "prices", conn, if_exists="replace", index=False
    )

    pd.read_csv(DATA_DIR / "promotions.csv").to_sql(
        "promotions", conn, if_exists="replace", index=False
    )

    conn.close()
    print("Database created successfully")

if __name__ == "__main__":
    load_csv_to_db()
