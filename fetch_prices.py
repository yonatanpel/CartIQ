import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path("data/cartiq.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def fetch_and_update_prices():
    print(f"[{datetime.datetime.now()}] Starting price update process...")
    
    # כאן בעתיד נכניס את הקוד שמתחבר לשרתי הרשתות (שופרסל, רמי לוי וכו')
    # ומוריד את קבצי ה-XML / JSON המעודכנים שלהם.
    
    # לשם ההדגמה והכנת התשתית, ניצור רשימת מחירים מעודכנת ש"משכנו" מהרשת:
    # (product_id, chain_id, price, last_update)
    updated_prices = [
        (1, 1, 5.90, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        (2, 1, 12.50, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        # ... הנתונים האמיתיים מה-XML יכנסו לכאן
    ]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # אפשרות 1: מחיקת המחירים הישנים והכנסת החדשים
        # cursor.execute("DELETE FROM prices")
        
        # אפשרות 2: עדכון מחירים קיימים או הוספת חדשים (Upsert)
        cursor.executemany("""
            INSERT INTO prices (product_id, chain_id, price, last_update)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(product_id, chain_id) 
            DO UPDATE SET price=excluded.price, last_update=excluded.last_update
        """, updated_prices)
        
        conn.commit()
        print("Prices updated successfully in cartiq.db!")
        
    except Exception as e:
        print(f"Error updating prices: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fetch_and_update_prices()
