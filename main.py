#!/usr/bin/env python3

import os
import requests
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PRODUCTS_FILE = 'products.json'

# Telegram API endpoints
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def load_products():
    """Load daftar produk dari file"""
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_products(products):
    """Simpan daftar produk ke file"""
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(products, f, indent=2)

def send_telegram_message(message):
    """Kirim pesan ke Telegram via API"""
    try:
        url = f"{TELEGRAM_API}/sendMessage"
        data = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def get_updates(offset=None):
    """Ambil updates dari Telegram"""
    try:
        url = f"{TELEGRAM_API}/getUpdates"
        params = {'timeout': 30}
        if offset:
            params['offset'] = offset
        response = requests.get(url, params=params, timeout=35)
        return response.json().get('result', [])
    except Exception as e:
        print(f"Error getting updates: {e}")
        return []

def get_current_price(platform, url):
    """Dapatkan harga saat ini dari produk"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        # Cari harga dalam format Rp (Tokopedia)
        match = re.search(r'Rp([\d.]+)', response.text)
        if match:
            price = int(match.group(1).replace('.', ''))
            return price
        
        # Cari harga Shopee
        match = re.search(r'"price":(\d+)', response.text)
        if match:
            return int(match.group(1))
        
        return None
    except Exception as e:
        print(f"Error scraping {platform}: {e}")
        return None

def format_price(price):
    """Format harga ke Rp"""
    return f"Rp{price:,.0f}".replace(',', '.')

def check_prices_job():
    """Job untuk cek harga otomatis"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking prices...")
    products = load_products()
    
    for product in products:
        try:
            price = get_current_price(product['platform'], product['url'])
            if price is None:
                continue
            
            product['current_price'] = price
            product['last_checked'] = datetime.now().isoformat()
            
            if price <= product['target_price']:
                message = f"""🎉 <b>HARGA TARGET TERCAPAI!</b>

📦 Produk: {product['name']}
🏪 Platform: {product['platform']}
💰 Harga Sekarang: <b>{format_price(price)}</b>
🎯 Target Harga: {format_price(product['target_price'])}

<a href="{product['url']}">Beli Sekarang</a>"""
                send_telegram_message(message)
            
            time.sleep(1)
        except Exception as e:
            print(f"Error checking {product.get('name')}: {e}")
    
    save_products(products)

def handle_command(text, update_id):
    """Handle perintah dari user"""
    parts = text.split(None, 3)
    command = parts[0]
    
    if command == '/start':
        message = """👋 Selamat datang di <b>Price Monitor Bot</b>!

<b>Perintah yang tersedia:</b>
/add_product - Tambah produk
/list_products - Lihat daftar
/remove_product [N] - Hapus produk
/check_now - Cek harga sekarang
/help - Bantuan

Ketik /help untuk detail"""
        send_telegram_message(message)
    
    elif command == '/help':
        message = """<b>📖 Panduan Penggunaan</b>

<b>1️⃣ Tambah Produk:</b>
<code>/add_product Tokopedia https://tokopedia.com/... 150000</code>

<b>2️⃣ Lihat Produk:</b>
<code>/list_products</code>

<b>3️⃣ Hapus Produk:</b>
<code>/remove_product 1</code>

<b>4️⃣ Cek Harga Sekarang:</b>
<code>/check_now</code>"""
        send_telegram_message(message)
    
    elif command == '/add_product':
        if len(parts) < 4:
            send_telegram_message("❌ Format: /add_product [Platform] [URL] [Harga]")
            return
        
        platform, url, target = parts[1], parts[2], parts[3]
        
        if platform.lower() not in ['tokopedia', 'shopee']:
            send_telegram_message("❌ Platform harus Tokopedia atau Shopee")
            return
        
        try:
            target_price = int(target)
        except:
            send_telegram_message("❌ Harga harus angka")
            return
        
        send_telegram_message("⏳ Cek harga...")
        current_price = get_current_price(platform, url)
        
        if current_price is None:
            send_telegram_message("❌ Tidak bisa cek harga. Cek URL!")
            return
        
        products = load_products()
        products.append({
            'id': len(products) + 1,
            'name': url.split('/')[-1][:50],
            'platform': platform,
            'url': url,
            'target_price': target_price,
            'current_price': current_price,
            'added_date': datetime.now().isoformat(),
            'last_checked': datetime.now().isoformat()
        })
        save_products(products)
        
        message = f"""✅ <b>Produk Ditambahkan!</b>

📦 Nama: {products[-1]['name']}
🏪 Platform: {platform}
💰 Harga Sekarang: {format_price(current_price)}
🎯 Target: {format_price(target_price)}

Bot akan cek harga setiap jam!"""
        send_telegram_message(message)
    
    elif command == '/list_products':
        products = load_products()
        if not products:
            send_telegram_message("📭 Belum ada produk")
            return
        
        message = "<b>📋 Daftar Produk</b>\n\n"
        for p in products:
            current = format_price(p.get('current_price', 0))
            target = format_price(p.get('target_price', 0))
            message += f"<b>{p['id']}. {p['name']}</b>\n   Platform: {p['platform']}\n   Harga: {current}\n   Target: {target}\n\n"
        
        send_telegram_message(message)
    
    elif command == '/remove_product':
        if len(parts) < 2:
            send_telegram_message("❌ Format: /remove_product [nomor]")
            return
        
        try:
            product_id = int(parts[1])
            products = load_products()
            products = [p for p in products if p['id'] != product_id]
            save_products(products)
            send_telegram_message(f"✅ Produk #{product_id} dihapus")
        except:
            send_telegram_message("❌ Nomor produk tidak valid")
    
    elif command == '/check_now':
        send_telegram_message("⏳ Cek harga...")
        products = load_products()
        alert_count = 0
        
        for product in products:
            try:
                price = get_current_price(product['platform'], product['url'])
                if price is None:
                    continue
                
                product['current_price'] = price
                
                if price <= product['target_price']:
                    message = f"""🎉 <b>HARGA TARGET TERCAPAI!</b>

📦 Produk: {product['name']}
🏪 Platform: {product['platform']}
💰 Harga: <b>{format_price(price)}</b>
🎯 Target: {format_price(product['target_price'])}

<a href="{product['url']}">Beli Sekarang</a>"""
                    send_telegram_message(message)
                    alert_count += 1
                
                time.sleep(1)
            except:
                pass
        
        save_products(products)
        if alert_count > 0:
            send_telegram_message(f"✅ {alert_count} produk mencapai target!")
        else:
            send_telegram_message("✅ Selesai. Tidak ada produk yang mencapai target")

def main():
    """Main bot loop"""
    print("🤖 Bot started!")
    print("Polling updates from Telegram...")
    
    # Setup scheduler untuk cek harga setiap jam
    scheduler = BlockingScheduler()
    scheduler.add_job(check_prices_job, 'interval', hours=1)
    
    # Jalankan scheduler di background thread
    from threading import Thread
    scheduler_thread = Thread(target=scheduler.start, daemon=True)
    scheduler_thread.start()
    
    # Polling updates
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            
            for update in updates:
                update_id = update.get('update_id')
                offset = update_id + 1
                
                message = update.get('message', {})
                text = message.get('text', '')
                
                if text and text.startswith('/'):
                    handle_command(text, update_id)
            
            time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n✅ Bot stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
