import sqlite3
import datetime
import requests
from bs4 import BeautifulSoup
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import io
import pandas as pd

DB_PATH = Path("data/cartiq.db")

# ID של הרשתות כפי שהן מופיעות במערכת הממשלתית
CHAINS_CONFIG = [
    {"id": "shufersal", "name": "שופרסל", "code": 7290027600007},
    {"id": "ramilevy", "name": "רמי לוי", "code": 7290058140886},
    {"id": "yohananof", "name": "יוחננוף", "code": 7290873255550},
    {"id": "victory", "name": "ויקטורי", "code": 7290691500006},
    {"id": "osherad", "name": "אושר עד", "code": 7290873255550}
]

def get_connection():
    return sqlite3.connect(DB_PATH)

def determine_category(product_name):
    # נשאר ללא שינוי, כפי שסיכמנו
    name = product_name.lower()
    if any(brand in name for brand in ["פינוק", "דאב", "dove", "פנטן", "הד אנד שולדרס", "קולגייט", "אורל בי", "קרליין", "לוריאל", "גרנייה", "נקה 7"]):
        return "טואלטיקה"
    elif any(brand in name for brand in ["תנובה", "טרה", "שטראוס", "יופלה", "דנונה", "יטבתה", "מולר"]):
        return "ביצים, חלב וגבינות"
    elif any(brand in name for brand in ["זוגלובק", "טירת צבי", "עוף טוב", "מילועוף"]):
        return "קצביה"
    elif any(k in name for k in ["ביצים", "חלב", "גבינה", "מעדן", "יוגורט", "שמנת"]):
        return "ביצים, חלב וגבינות"
    elif any(k in name for k in ["עוף", "בשר", "דג", "נקניק", "קצביה"]):
        return "קצביה"
    elif any(k in name for k in ["קפוא", "שניצל", "ירקות קפואים", "פיצה קפואה", "בורקס קפוא"]):
        return "מוצרים קפואים"
    elif any(k in name for k in ["לחם", "פיתה", "עוגות", "מאפה"]):
        return "מאפים ולחם"
    elif any(k in name for k in ["בושם", "הגיינה", "סבון", "שמפו", "מרכך", "דאודורנט"]):
        return "טואלטיקה"
    elif any(k in name for k in ["אקונומיקה", "ניקוי", "שקיות אשפה", "סבון כלים", "רצפה", "מנקה"]):
        return "מוצרי ניקוי"
    elif any(k in name for k in ["חד פעמי", "מפה", "מפית", "אירוח"]):
        return "אירוח"
    elif any(k in name for k in ["קמח", "פסטה", "פתיתים", "אורז", "שימורים", "סוכר", "מלח", "אפייה", "שמן", "רטבים", "קטניות"]):
        return "מזווה"
    elif any(k in name for k in ["עגבני", "מלפפון", "גזר", "פלפל", "בצל"]):
        return "ירקות"
    elif any(k in name for k in ["תפוח", "בננה", "תפוז", "אגס", "אבוקדו"]):
        return "פירות"
    return "כללי"

def fetch_chain_data(chain):
    # הכתובת הרשמית של ה-PriceFull לפי הקוד הממשלתי
    base_gov_url = f"https://prices.moital.gov.il/FileObject/UpdateCategory?catID=2&storeId={chain['code']}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(base_gov_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # מחפשים את הלינק לקובץ ה-XML/GZ בתוך פורטל השקיפות
        for a in soup.find_all('a', href=True):
            if 'pricefull' in a['href'].lower():
                download_link = a['href']
                print(f"Downloading for {chain['name']}...")
                file_response = requests.get(download_link, headers=headers, timeout=120)
                compressed_file = io.BytesIO(file_response.content)
                xml_content = gzip.GzipFile(fileobj=compressed_file).read()
                parse_and_store_xml(xml_content, chain['code'])
                break
    except Exception as e:
        print(f"Error for {chain['name']}: {e}")

def parse_and_store_xml(xml_content, chain_id):
    root = ET.fromstring(xml_content)
    conn = get_connection()
    cursor = conn.cursor()
    # ... (המשך הלוגיקה שלך ל-INSERT OR REPLACE נשארת זהה)
    # מוודא שאתה שומר את ה-chain_id בטבלת המחירים!
    products_to_upsert = []
    prices_to_upsert = []
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in root.findall(".//Item"):
        try:
            p_id = item.find("ItemCode").text
            p_name = item.find("ItemName").text
            category = determine_category(p_name)
            price = float(item.find("ItemPrice").text)
            if price > 0:
                products_to_upsert.append((p_id, p_name, category, "לא צוין", "יחידה"))
                prices_to_upsert.append((p_id, chain_id, price, current_time))
        except: continue
    
    cursor.executemany("INSERT OR REPLACE INTO products (product_id, product_name, category, brand, unit) VALUES (?, ?, ?, ?, ?)", products_to_upsert)
    cursor.executemany("INSERT OR REPLACE INTO prices (product_id, chain_id, price, update_time) VALUES (?, ?, ?, ?)", prices_to_upsert)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    for chain in CHAINS_CONFIG:
        fetch_chain_data(chain)
