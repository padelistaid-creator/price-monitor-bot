#!/usr/bin/env python3

import os
import requests
import json
import time
import re
import random
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from threading import Thread

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

import random

# Global session untuk reuse connection
requests_session = requests.Session()

def scrape_harga(url):
    """Coba scrape harga dari URL dengan improved strategy"""
    try:
        # Real browser headers yang lebih lengkap
        headers = {
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Random delay untuk mimick human browsing (2-5 detik)
        time.sleep(random.uniform(2, 5))
        
        print(f"[SCRAPING] {url[:60]}...")
        
        # Gunakan session untuk reuse connection
        response = requests_session.get(
            url,
            headers=headers,
            timeout=15,
            allow_redirects=True
        )
        
        # Check status code
        if response.status_code == 403:
            print(f"[ERROR] 403 Forbidden - Website block request")
            return None
        elif response.status_code == 429:
            print(f"[ERROR] 429 Too Many Requests - Rate limited")
            return None
        elif response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code}")
            return None
        
        response.raise_for_status()
        html = response.text
        
        print(f"[DEBUG] Got {len(html)} bytes")
        
        # Tokopedia - cari berbagai pattern
        patterns = [
            r'Rp[\s]*([0-9.]+)',  # Rp 1.000.000
            r'"price":(\d+)',      # "price":1000000
            r'"finalPrice":(\d+)', # "finalPrice":1000000
            r'"originalPrice":(\d+)',  # original price
            r'Rp\s*(\d+(?:\.\d+)*)',  # Alternative Rp format
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                price_str = match.group(1)
                try:
                    # Remove dots and convert
                    price = int(price_str.replace('.', '').replace(',', ''))
                    if price > 1000 and price < 1000000000:  # Sanity check
                        print(f"[SUCCESS] Found price: Rp {price:,}")
                        return price
                except:
                    continue
        
        print(f"[WARNING] Could not find valid price pattern")
        return None
        
    except requests.exceptions.Timeout:
        print(f"[ERROR] Timeout (15s) - Website slow or blocked")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Connection error")
        return None
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return None

def format_price(price):
    """Format harga ke Rp"""
    if isinstance(price, int):
        return f"Rp{price:,.0f}".replace(',', '.')
    return str(price)

def check_prices_job():
    """Job untuk cek harga otomatis"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] AUTO-CHECK HARGA")
    products = load_products()
    
    if not products:
        return
    
    for product in products:
        try:
            # Skip jika harga manual (user set sendiri)
            if product.get('manual_price'):
                continue
            
            price = scrape_harga(product['url'])
            if price is None:
                print(f"  ⚠️ {product['name']} - Gagal scrape")
                continue
            
            product['current_price'] = price
            product['last_checked'] = datetime.now().isoformat()
            
            print(f"  ✓ {product['name']} - Rp {price:,}")
            
            # Alert jika harga target tercapai
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
            print(f"  ❌ Error checking {product.get('name')}: {e}")
    
    save_products(products)

def handle_command(text, update_id):
    """Handle perintah dari user"""
    parts = text.split(None, 4)
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

<b>Format:</b>
/add_product [Platform] [URL] [Target_Harga]

<b>2️⃣ Lihat Produk:</b>
<code>/list_products</code>

<b>3️⃣ Hapus Produk:</b>
<code>/remove_product 1</code>

<b>4️⃣ Cek Harga Sekarang:</b>
<code>/check_now</code>

<b>⚠️ Tips:</b>
- URL harus dari address bar (bukan link share)
- Harga target dalam Rupiah (angka saja)
- Bot cek otomatis setiap jam"""
        send_telegram_message(message)
    
    elif command == '/add_product':
        if len(parts) < 4:
            send_telegram_message("❌ Format: /add_product [Platform] [URL] [Harga]\n\nContoh: /add_product Tokopedia https://tokopedia.com/toko/produk 5000000")
            return
        
        platform, url, target = parts[1], parts[2], parts[3]
        
        if platform.lower() not in ['tokopedia', 'shopee']:
            send_telegram_message("❌ Platform harus: Tokopedia atau Shopee")
            return
        
        try:
            target_price = int(target)
            if target_price <= 0:
                raise ValueError()
        except:
            send_telegram_message("❌ Harga harus angka positif")
            return
        
        if not url.startswith('http'):
            send_telegram_message("❌ URL harus dimulai dengan http:// atau https://")
            return
        
        send_telegram_message("⏳ Sedang cek harga dari website...")
        current_price = scrape_harga(url)
        
        if current_price is None:
            send_telegram_message("""❌ <b>Gagal ambil harga dari website</b>

Kemungkinan:
1️⃣ Website memblokir bot (anti-scraping)
2️⃣ URL tidak valid atau produk sudah dihapus
3️⃣ Harga di-load via JavaScript (bot tidak bisa)

<b>Solusi:</b>
- Tunggu 15 menit dan coba lagi
- Pastikan URL dari address bar (bukan link share)
- Coba produk lain

Atau gunakan: /add_manual [Platform] [Nama] [Harga_Saat_Ini] [Target]""")
            return
        
        products = load_products()
        product_name = url.split('/')[-1][:50] if url.split('/')[-1] else 'Produk'
        
        new_product = {
            'id': len(products) + 1,
            'name': product_name,
            'platform': platform,
            'url': url,
            'target_price': target_price,
            'current_price': current_price,
            'added_date': datetime.now().isoformat(),
            'last_checked': datetime.now().isoformat(),
            'manual_price': False
        }
        products.append(new_product)
        save_products(products)
        
        message = f"""✅ <b>Produk Ditambahkan!</b>

📦 Nama: {product_name}
🏪 Platform: {platform}
💰 Harga Sekarang: {format_price(current_price)}
🎯 Target Harga: {format_price(target_price)}

Bot akan cek harga otomatis setiap jam!
Notifikasi akan dikirim saat harga turun ke target."""
        send_telegram_message(message)
    
    elif command == '/add_manual':
        if len(parts) < 5:
            send_telegram_message("❌ Format: /add_manual [Platform] [Nama] [Harga_Sekarang] [Target]\n\nContoh: /add_manual Tokopedia iPhone 5000000 4500000")
            return
        
        platform, name, current, target = parts[1], parts[2], parts[3], parts[4]
        
        try:
            current_price = int(current)
            target_price = int(target)
        except:
            send_telegram_message("❌ Harga harus angka")
            return
        
        products = load_products()
        new_product = {
            'id': len(products) + 1,
            'name': name,
            'platform': platform,
            'url': '',
            'target_price': target_price,
            'current_price': current_price,
            'added_date': datetime.now().isoformat(),
            'last_checked': datetime.now().isoformat(),
            'manual_price': True
        }
        products.append(new_product)
        save_products(products)
        
        message = f"""✅ <b>Produk Manual Ditambahkan!</b>

📦 Nama: {name}
🏪 Platform: {platform}
💰 Harga Sekarang: {format_price(current_price)}
🎯 Target Harga: {format_price(target_price)}

⚠️ Mode Manual - Anda harus update harga dengan:
/update_price [ID] [Harga_Baru]"""
        send_telegram_message(message)
    
    elif command == '/update_price':
        if len(parts) < 3:
            send_telegram_message("❌ Format: /update_price [ID] [Harga_Baru]")
            return
        
        try:
            product_id = int(parts[1])
            new_price = int(parts[2])
            
            products = load_products()
            for p in products:
                if p['id'] == product_id:
                    p['current_price'] = new_price
                    p['last_checked'] = datetime.now().isoformat()
                    
                    if new_price <= p['target_price']:
                        message = f"""🎉 <b>HARGA TARGET TERCAPAI!</b>

📦 Produk: {p['name']}
🏪 Platform: {p['platform']}
💰 Harga: <b>{format_price(new_price)}</b>
🎯 Target: {format_price(p['target_price'])}"""
                        send_telegram_message(message)
                    
                    save_products(products)
                    send_telegram_message(f"✅ Harga {p['name']} diupdate menjadi {format_price(new_price)}")
                    return
            
            send_telegram_message(f"❌ Produk #{product_id} tidak ditemukan")
        except:
            send_telegram_message("❌ Format tidak valid")
    
    elif command == '/list_products':
        products = load_products()
        if not products:
            send_telegram_message("📭 Belum ada produk")
            return
        
        message = "<b>📋 Daftar Produk</b>\n\n"
        for p in products:
            current = format_price(p.get('current_price', 0))
            target = format_price(p.get('target_price', 0))
            manual = " (Manual)" if p.get('manual_price') else ""
            message += f"<b>{p['id']}. {p['name']}</b>{manual}\n"
            message += f"   Platform: {p['platform']}\n"
            message += f"   Harga: {current}\n"
            message += f"   Target: {target}\n\n"
        
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
        send_telegram_message("⏳ Sedang cek harga semua produk...")
        products = load_products()
        alert_count = 0
        
        for product in products:
            if product.get('manual_price'):
                continue
            
            try:
                price = scrape_harga(product['url'])
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
        send_telegram_message(f"✅ Pengecekan selesai. {alert_count} produk mencapai target.")

def main():
    """Main bot loop"""
    print("🤖 Bot started!")
    print("Polling updates from Telegram...\n")
    
    # Setup scheduler untuk cek harga setiap jam
    scheduler = BlockingScheduler()
    scheduler.add_job(check_prices_job, 'interval', hours=1, id='price_check')
    
    # Jalankan scheduler di background thread
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
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Command: {text[:50]}")
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
