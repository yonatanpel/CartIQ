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
CATEGORIES_FILE = Path("data/categories.csv") 

def get_connection():
    return sqlite3.connect(DB_PATH)

def load_category_mapping():
    if not CATEGORIES_FILE.exists():
        return {}
    try:
        df = pd.read_csv(CATEGORIES_FILE)
        # מחזיר מילון שבו המפתח הוא מילת המפתח והערך הוא הקטגוריה
        return dict(zip(df['keyword'].str.lower(), df['category']))
    except Exception as e:
        print(f"Error loading categories.csv: {e}")
        return {}

def determine_category(product_name):
    name = product_name.lower()

    # --- שכבה 1: מותגים (סדר עדיפות עליון) ---
    
    # טואלטיקה ופארם - אם מותג מזוהה כאן, זהו זה, לא ממשיך הלאה
    if any(brand in name for brand in ["פינוק", "דאב", "dove", "פנטן", "הד אנד שולדרס", "קולגייט", "אורל בי", "קרליין", "לוריאל", "גרנייה", "נקה 7", "פיניש"]):
        return "טואלטיקה וניקוי"
    
    # חלב - אם מותג מזוהה כאן, עוצר
    elif any(brand in name for brand in ["תנובה", "טרה", "שטראוס", "יופלה", "דנונה", "יטבתה", "מולר"]):
        return "מוצרי חלב וביצים"
        
    # בשר - אם מותג מזוהה כאן, עוצר
    elif any(brand in name for brand in ["זוגלובק", "טירת צבי", "עוף טוב", "מילועוף"]):
        return "עוף, בשר, דגים"

    # --- שכבה 2: מילות מפתח (רק אם לא נמצא מותג) ---
    
    elif any(keyword in name for keyword in ["סבון", "שמפו", "מרכך", "דאודורנט", "אקונומיקה", "כביסה"]):
        return "טואלטיקה וניקוי"
        
    elif any(keyword in name for keyword in ["עגבני", "מלפפון", "גזר", "פלפל", "בצל"]):
        return "ירקות טריים"
    
    elif any(keyword in name for keyword in ["תפוח", "בננה", "תפוז", "אגס", "אבוקדו"]):
        return "פירות טריים"

    elif any(keyword in name for keyword in ["עוף", "בשר", "דג", "נקניק"]):
        return "עוף, בשר, דגים"
        
    elif any(keyword in name for keyword in ["לחם", "פיתה", "עוגות"]):
        return "מאפה ולחם"

    else:
        return "מזווה וכללי"
def fetch_shufersal_real_prices(store_id="1", chain_id=1):
    print(f"[{datetime.datetime.now()}] Connecting to Shufersal...")
    base_url = "http://prices.shufersal.co.il"
    search_url = f"{base_url}/FileObject/UpdateCategory?catID=2&storeId={store_id}"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        download_link = None
        for a in soup.find_all('a', href=True):
            if 'pricefull' in a['href'].lower() and 'gz' in a['href'].lower():
                download_link = base_url + a['href'] if a['href'].startswith('/') else a['href']
                break
        
        if not download_link:
            print("Could not find PriceFull file.")
            return

        file_response = requests.get(download_link, headers=headers, timeout=120)
        compressed_file = io.BytesIO(file_response.content)
        xml_content = gzip.GzipFile(fileobj=compressed_file).read()
        parse_and_store_xml(xml_content, chain_id)
        
    except Exception as e:
        print(f"Error: {e}")

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
    fetch_shufersal_real_prices()
