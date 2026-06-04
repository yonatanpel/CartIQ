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
    print(f"[{datetime.datetime.now()}] Connecting to Shufersal portal for store {store_id}...")
    
    base_url = "http://prices.shufersal.co.il"
    search_url = f"{base_url}/FileObject/UpdateCategory?catID=2&storeId={store_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to connect to Shufersal: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    download_link = None
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        href_lower = href.lower()
        
        if 'pricefull' in href_lower and ('gz' in href_lower or 'zip' in href_lower):
            download_link = href
            if download_link.startswith('/'):
                download_link = base_url + download_link
            break
            
    if not download_link:
        print("Could not find today's PriceFull file.")
        return

    print(f"Success! Downloading latest price file: {download_link}")
    
    try:
        # הקובץ גדול, אז נותנים לו יותר זמן לרדת (timeout=120)
        file_response = requests.get(download_link, headers=headers, timeout=120)
        print("Decompressing file and parsing XML...")
        compressed_file = io.BytesIO(file_response.content)
        
        decompressed_file = gzip.GzipFile(fileobj=compressed_file)
        xml_content = decompressed_file.read()
        parse_and_store_xml(xml_content, chain_id)
    except Exception as e:
        print(f"Error during download or extraction: {e}")

def parse_and_store_xml(xml_content, chain_id):
    print("Starting XML parsing...")
    root = ET.fromstring(xml_content)
    conn = get_connection()
    cursor = conn.cursor()

    products_to_upsert = []
    prices_to_upsert = []
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            
            if price <= 0:
                continue

            products_to_upsert.append((product_id, product_name, "כללי", brand, unit))
            prices_to_upsert.append((product_id, chain_id, price, current_time))
            
        except Exception as e:
            continue

    print("Saving products to database...")
    cursor.executemany("""
        INSERT INTO products (product_id, product_name, category, brand, unit)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            product_name=excluded.product_name,
            brand=excluded.brand,
            unit=excluded.unit
    """, products_to_upsert)

    print("Saving prices to database...")
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
    fetch_shufersal_real_prices(store_id="1", chain_id=1)
