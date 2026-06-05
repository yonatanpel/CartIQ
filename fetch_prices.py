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

# שימוש בכתובות ישירות ופעילות לקבצי ה-XML של הרשתות
CHAINS_CONFIG = [
    {"id": 7290027600007, "name": "שופרסל", "url": "http://prices.shufersal.co.il/FileObject/UpdateCategory?catID=2"},
    {"id": 7290058140886, "name": "רמי לוי", "url": "https://url.rami-levy.co.il/FileObject/UpdateCategory?catID=2"},
    {"id": 7290873255550, "name": "יוחננוף", "url": "https://yohananof.co.il/FileObject/UpdateCategory?catID=2"},
    {"id": 7290691500006, "name": "ויקטורי", "url": "https://victory.co.il/FileObject/UpdateCategory?catID=2"},
    {"id": 7290873255550, "name": "אושר עד", "url": "https://osherad.co.il/FileObject/UpdateCategory?catID=2"}
]

def get_connection():
    return sqlite3.connect(DB_PATH)

def determine_category(product_name):
    name = product_name.lower()
    # "קיר ברזל" מותגים
    if any(brand in name for brand in ["פינוק", "דאב", "dove", "פנטן", "הד אנד שולדרס", "קולגייט", "אורל בי", "קרליין", "לוריאל", "גרנייה", "נקה 7"]):
        return "טואלטיקה"
    elif any(brand in name for brand in ["תנובה", "טרה", "שטראוס", "יופלה", "דנונה", "יטבתה", "מולר"]):
        return "ביצים, חלב וגבינות"
    elif any(brand in name for brand in ["זוגלובק", "טירת צבי", "עוף טוב", "מילועוף"]):
        return "קצביה"
    # מילות מפתח
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
    print(f"[{datetime.datetime.now()}] Connecting to {chain['name']}...")
    # הוספת headers של דפדפן כדי לא להיחסם
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    try:
        response = requests.get(chain['url'], headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        download_link = None
        for a in soup.find_all('a', href=True):
            if 'pricefull' in a['href'].lower() and 'gz' in a['href'].lower():
                download_link = a['href'] if a['href'].startswith('http') else chain['url'].split('/FileObject')[0] + a['href']
                break
        
        if download_link:
            print(f"Downloading: {download_link}")
            file_response = requests.get(download_link, headers=headers, timeout=120)
            compressed_file = io.BytesIO(file_response.content)
            xml_content = gzip.GzipFile(fileobj=compressed_file).read()
            parse_and_store_xml(xml_content, chain['id'])
        else:
            print(f"Could not find PriceFull file for {chain['name']}")
    except Exception as e:
        print(f"Error for {chain['name']}: {e}")

def parse_and_store_xml(xml_content, chain_id):
    root = ET.fromstring(xml_content)
    conn = get_connection()
    cursor = conn.cursor()
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
    print("Database updated successfully!")

if __name__ == "__main__":
    for chain in CHAINS_CONFIG:
        fetch_chain_data(chain)
