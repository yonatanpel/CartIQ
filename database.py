import sqlite3
from pathlib import Path

DB_PATH = Path("data/cartiq.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        brand TEXT,
        unit TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chains (
        chain_id INTEGER PRIMARY KEY,
        chain_name TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        product_id INTEGER,
        chain_id INTEGER,
        price REAL,
        last_update TEXT,
        PRIMARY KEY (product_id, chain_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promotions (
        promotion_id INTEGER PRIMARY KEY,
        product_id INTEGER,
        chain_id INTEGER,
        promotion_type TEXT,
        discount_value REAL,
        start_date TEXT,
        end_date TEXT
    )
    """)

    conn.commit()
    conn.close()
