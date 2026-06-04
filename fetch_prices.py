import sqlite3
import datetime
import requests
import xml.etree.ElementTree as ET
import gzip
from pathlib import Path

DB_PATH = Path("data/cartiq.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def parse_and_store_xml(xml_content, chain_id):
    """
    פונקציה שמקבלת תוכן של קובץ XML רשמי של חוק המזון,
    מחלצת את המוצרים והמחירים, ומעדכנת את מסד הנתונים.
    """
    print(f"Parsing XML data for Chain ID: {chain_id}...")
    
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML string: {e}")
        return

    conn = get_connection()
    cursor = conn.cursor()

    products_to_upsert = []
    prices_to_upsert = []
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # חוק המזון מגדיר שכל המוצרים נמצאים תחת התגית <Items>/<Item>
    items = root.findall(".//Item")
    print(f"Found {len(items)} items in the file.")

    for item in items:
        try:
            # חילוץ נתונים על פי השדות הקבועים בחוק
            product_id = item.find("ItemCode").text
            product_name = item.find("ItemName").text
            brand = item.find("ManufactureName").text if item.find("ManufactureName") is not None else "לא ידוע"
            unit = item.find("UnitOfMeasure").text if item.find("UnitOfMeasure") is not None else "יחידה"
            price = float(item.find("ItemPrice").text)
            
            # קביעת קטגוריה בסיסית (בנתוני האמת אין קטגוריה, נגדיר כברירת מחדל או נחלץ לפי שם)
            category = "כללי"
            
            # הכנת נתונים לטבלת מוצרים
            products_to_upsert.append((product_id, product_name, category, brand, unit))
            
            # הכנת נתונים לטבלת מחירים
            prices_to_upsert.append((product_id, chain_id, price, current_time))
            
        except Exception as e:
            # אם יש מוצר פגום בקובץ, נדלג עליו ונמשיך
            continue

    # 1. עדכון או הוספת מוצרים (Products)
    cursor.executemany("""
        INSERT INTO products (product_id, product_name, category, brand, unit)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            product_name=excluded.product_name,
            brand=excluded.brand,
            unit=excluded.unit
    """, products_to_upsert)

    # 2. עדכון או הוספת מחירים (Prices)
    cursor.executemany("""
        INSERT INTO prices (product_id, chain_id, price, last_update)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(product_id, chain_id) DO UPDATE SET
            price=excluded.price,
            last_update=excluded.last_update
    """, prices_to_upsert)

    conn.commit()
    conn.close()
    print(f"Successfully database updated with {len(prices_to_upsert)} prices.")

def fetch_live_data():
    """
    הפונקציה המרכזית שמורידה את הקבצים מהרשתות ומפעילה את המפרסר
    """
    print(f"[{datetime.datetime.now()}] Starting live price update...")
    
    # ברשתות הקמעונאות הלינקים משתנים או דורשים התחברות לשרתי ה-FTP שלהם.
    # לצורך הדוגמה החיה והבדיקה, נשתמש בקישור לקובץ מחירים לדוגמה שעומד בתקן חוק המזון.
    # בעתיד ניתן להוסיף כאן לולאה שעוברת על ה-URLs של שופרסל, רמי לוי וכו'.
    
    urls_to_fetch = [
        {"chain_id": 1, "url": "https://raw.githubusercontent.com/israeli-supermarket-scraper/israeli-supermarket-scraper/master/tests/mocks/price_full_mock.xml"}
    ]
    
    for target in urls_to_fetch:
        try:
            response = requests.get(target["url"], timeout=30)
            if response.status_code == 200:
                # בדיקה האם הקובץ מכווץ (הרבה רשתות מעלות כקובץ gz)
                if target["url"].endswith(".gz"):
                    xml_content = gzip.decompress(response.content).decode('utf-8')
                else:
                    xml_content = response.text
                
                parse_and_store_xml(xml_content, target["chain_id"])
            else:
                print(f"Failed to download file from {target['url']}, Status: {response.status_code}")
        except Exception as e:
            print(f"Error fetching data from {target['url']}: {e}")

if __name__ == "__main__":
    fetch_live_data()
