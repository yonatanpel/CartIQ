import sqlite3
import datetime
import requests
from bs4 import BeautifulSoup
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import io

DB_PATH = Path("data/cartiq.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def fetch_shufersal_real_prices(store_id="1", chain_id=1):
    """
    מתחבר לאתר שקיפות המחירים של שופרסל,
    מאתר את הקובץ המלא (PriceFull) של היום עבור סניף ספציפי,
    מוריד, פותח את הכיווץ ומעדכן את מסד הנתונים.
    """
    print(f"[{datetime.datetime.now()}] Connecting to Shufersal portal for store {store_id}...")
    
    # הכתובת הרשמית שבה שופרסל מפרסמת את הקבצים (catID=2 מציין קבצי מחירים)
    base_url = "http://prices.shufersal.co.il"
    search_url = f"{base_url}/FileObject/UpdateCategory?catID=2&storeId={store_id}"
    
    # אנחנו מגדירים 'User-Agent' כדי שהאתר לא יחשוב שאנחנו רובוט זדוני ויחסום אותנו
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(search_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error accessing Shufersal website. Status: {response.status_code}")
        return

    # 1. סורקים את קוד ה-HTML של האתר כדי למצוא את הקישור העדכני לקובץ המחירים המלא
    soup = BeautifulSoup(response.text, 'html.parser')
    download_link = None
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'PriceFull' in href and href.endswith('.gz'):
            download_link = href
            break
            
    if not download_link:
        print("Could not find today's PriceFull file.")
        return

    print(f"Downloading latest price file: {download_link}")
    
    # 2. הורדת הקובץ המכווץ
    file_response = requests.get(download_link, headers=headers)
    
    print("Decompressing GZ file and parsing XML...")
    compressed_file = io.BytesIO(file_response.content)
    
    try:
        # 3. פתיחת הכיווץ (.gz) בזמן אמת והעברת התוכן למפרסר
        decompressed_file = gzip.GzipFile(fileobj=compressed_file)
        xml_content = decompressed_file.read()
        parse_and_store_xml(xml_content, chain_id)
    except Exception as e:
        print(f"Error decompressing or parsing file: {e}")

def parse_and_store_xml(xml_content, chain_id):
    """קריאת הנתונים מתוך ה-XML והכנסתם לטבלאות שלנו ב-SQLite"""
    root = ET.fromstring(xml_content)
    conn = get_connection()
    cursor = conn.cursor()

    products_to_upsert = []
    prices_to_upsert = []
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # במבנה ה-XML של חוק המזון, כל מוצר נמצא בתוך תגית <Item>
    items = root.findall(".//Item")
    print(f"Found {len(items)} items in the XML file.")

    for item in items:
        try:
            product_id = item.find("ItemCode").text
            product_name = item.find("ItemName").text
            
            manufacture = item.find("ManufactureName")
            brand = manufacture.text if manufacture is not None and manufacture.text else "לא צוין"
            
            unit_elem = item.find("UnitOfMeasure")
            unit = unit_elem.text if unit_elem is not None and unit_elem.text else "יחידה"
            
            price_elem = item.find("ItemPrice")
            price = float(price_elem.text) if price_elem is not None else 0.0
            
            # מדלגים על מוצרים שהמחיר שלהם 0 או שגוי
            if price <= 0:
                continue

            products_to_upsert.append((product_id, product_name, "כללי", brand, unit))
            prices_to_upsert.append((product_id, chain_id, price, current_time))
            
        except Exception as e:
            # אם יש שורה שבורה ב-XML, נדלג עליה ונמשיך למוצר הבא
            continue

    # הכנסה / עדכון של טבלת המוצרים
    cursor.executemany("""
        INSERT INTO products (product_id, product_name, category, brand, unit)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            product_name=excluded.product_name,
            brand=excluded.brand,
            unit=excluded.unit
    """, products_to_upsert)

    # הכנסה / עדכון של טבלת המחירים
    cursor.executemany("""
        INSERT INTO prices (product_id, chain_id, price, last_update)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(product_id, chain_id) DO UPDATE SET
            price=excluded.price,
            last_update=excluded.last_update
    """, prices_to_upsert)

    conn.commit()
    conn.close()
    print(f"Successfully updated database with {len(prices_to_upsert)} prices for Chain ID {chain_id}!")

if __name__ == "__main__":
    # הפעלת הסקריפט על סניף מס' 1 (נניח מוגדר אצלנו כשופרסל, chain_id=1)
    fetch_shufersal_real_prices(store_id="1", chain_id=1)
