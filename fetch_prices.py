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

# הגדרת הרשתות
CHAINS_CONFIG = [
    {"id": 1, "name": "שופרסל", "url": "http://prices.shufersal.co.il"},
    {"id": 2, "name": "רמי לוי", "url": "http://prices.rami-levy.co.il"},
    {"id": 3, "name": "יוחננוף", "url": "http://prices.yohananof.co.il"},
    {"id": 4, "name": "ויקטורי", "url": "http://prices.victory.co.il"},
    {"id": 5, "name": "אושר עד", "url": "http://prices.osherad.co.il"}
]

def get_connection():
    return sqlite3.connect(DB_PATH)

def determine_category(product_name):
    name = product_name.lower()

    # --- 1. שכבת המותגים (קיר ברזל) ---
    if any(brand in name for brand in ["פינוק", "דאב", "dove", "פנטן", "הד אנד שולדרס", "קולגייט", "אורל בי", "קרליין", "לוריאל", "גרנייה", "נקה 7"]):
        return "טואלטיקה"
    elif any(brand in name for brand in ["תנובה", "טרה", "שטראוס", "יופלה", "דנונה", "יטבתה", "מולר"]):
        return "ביצים, חלב וגבינות"
    elif any(brand in name for brand in ["זוגלובק", "טירת צבי", "עוף טוב", "מילועוף"]):
        return "קצביה"

    # --- 2. שכבת הקטגוריות (מילות מפתח) ---
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
    search_url = f"{chain['url']}/FileObject/UpdateCategory?catID=2"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        download_link = None
        for a in soup.find_all('a', href=True):
            if 'pricefull' in a['href'].lower() and 'gz' in a['href'].lower():
                download_link = chain['url'] + a['href'] if a['href'].startswith('/') else a['href']
                break
        
        if not download_link:
            print(f"Could not find PriceFull file for {chain['name']}")
            return

        file_response = requests.get(download_link, headers=headers, timeout=120)
        compressed_file = io.BytesIO(file_response.content)
        xml_content = gzip.GzipFile(fileobj=compressed_file).read()
        parse_and_store_xml(xml_content, chain['id'])
        
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
            brand = item.find("ManufactureName").text if item.find("ManufactureName") is not None else "לא צוין"
            unit = item.find("UnitOfMeasure").text if item.find("UnitOfMeasure") is not None else "יחידה"
            price = float(item.find("ItemPrice").text)
            
            if price > 0:
                products_to_upsert.append((p_id, p_name, category, brand, unit))
                prices_to_upsert.append((p_id, chain_id, price, current_time))
        except:
            continue

    cursor.executemany("INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?)", products_to_upsert)
    cursor.executemany("INSERT OR REPLACE INTO prices VALUES (?, ?, ?, ?)", prices_to_upsert)
    conn.commit()
    conn.close()
    print("Database updated successfully!")

if __name__ == "__main__":
    for chain in CHAINS_CONFIG:
        fetch_chain_data(chain)
