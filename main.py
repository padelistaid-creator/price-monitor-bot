#!/usr/bin/env python3

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import requests
import json
import time
from datetime import datetime
import re

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID'))

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File untuk simpan data produk
PRODUCTS_FILE = 'products.json'

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
    try:
        with open(PRODUCTS_FILE, 'w') as f:
            json.dump(products, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving products: {e}")

def get_current_price(platform, url):
    """Dapatkan harga saat ini dari produk"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Cari harga dalam format Rp (untuk Tokopedia)
        match = re.search(r'Rp([\d.]+)', response.text)
        if match:
            price = int(match.group(1).replace('.', ''))
            return price
        
        # Cari harga tanpa Rp (untuk Shopee)
        match = re.search(r'"price":(\d+)', response.text)
        if match:
            price = int(match.group(1))
            return price
        
        return None
    except Exception as e:
        logger.error(f"Error scraping {platform}: {e}")
        return None

async def send_message(application: Application, message: str):
    """Kirim pesan ke user"""
    try:
        await application.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error sending message: {e}")

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /start"""
    message = """
👋 Selamat datang di <b>Price Monitor Bot</b>!

Bot ini akan memantau harga produk di Tokopedia dan Shopee, kemudian memberitahu Anda saat harga turun ke target.

<b>Perintah yang tersedia:</b>
/add_product - Tambah produk untuk dipantau
/list_products - Lihat daftar produk
/remove_product - Hapus produk
/check_now - Cek harga sekarang
/help - Tampilkan bantuan

Ketik /help untuk instruksi lebih detail.
"""
    await update.message.reply_text(message, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /help"""
    message = """
<b>📖 Panduan Penggunaan</b>

<b>1️⃣ Tambah Produk:</b>
<code>/add_product Tokopedia https://tokopedia.com/toko/produk 150000</code>

Format: /add_product [Platform] [URL] [Target Harga]
- Platform: Tokopedia atau Shopee
- Target Harga: Dalam Rupiah (angka saja)

<b>2️⃣ Lihat Semua Produk:</b>
<code>/list_products</code>

<b>3️⃣ Hapus Produk:</b>
<code>/remove_product 1</code>
(Ganti 1 dengan nomor produk)

<b>4️⃣ Cek Harga Sekarang:</b>
<code>/check_now</code>

<b>💡 Tips:</b>
- Gunakan URL produk yang lengkap
- Harga target sebaiknya 10-20% di bawah harga saat ini
- Gunakan /check_now untuk cek harga kapan saja
"""
    await update.message.reply_text(message, parse_mode='HTML')

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /add_product"""
    try:
        args = update.message.text.split(None, 3)
        
        if len(args) < 4:
            await update.message.reply_text(
                "❌ Format salah!\n\n"
                "Gunakan: /add_product [Platform] [URL] [Target Harga]\n\n"
                "Contoh:\n"
                "/add_product Tokopedia https://tokopedia.com/toko/produk 150000"
            )
            return
        
        platform = args[1]
        url = args[2]
        target_price = int(args[3])
        
        if platform.lower() not in ['tokopedia', 'shopee']:
            await update.message.reply_text("❌ Platform harus Tokopedia atau Shopee")
            return
        
        if target_price <= 0:
            await update.message.reply_text("❌ Harga harus lebih dari 0")
            return
        
        await update.message.reply_text("⏳ Sedang cek harga produk...")
        current_price = get_current_price(platform, url)
        
        if current_price is None:
            await update.message.reply_text(
                "❌ Tidak bisa cek harga produk.\n"
                "Pastikan URL benar dan produk tersedia."
            )
            return
        
        product_name = url.split('/')[-1][:50]
        
        products = load_products()
        new_product = {
            'id': len(products) + 1,
            'name': product_name,
            'platform': platform,
            'url': url,
            'target_price': target_price,
            'current_price': current_price,
            'added_date': datetime.now().isoformat(),
            'last_checked': datetime.now().isoformat()
        }
        products.append(new_product)
        save_products(products)
        
        current_formatted = f"Rp{current_price:,.0f}".replace(',', '.')
        target_formatted = f"Rp{target_price:,.0f}".replace(',', '.')
        
        message = f"""
✅ <b>Produk Ditambahkan!</b>

📦 Nama: {product_name}
🏪 Platform: {platform}
💰 Harga Sekarang: {current_formatted}
🎯 Target Harga: {target_formatted}

Gunakan /check_now untuk cek harga kapan saja.
"""
        await update.message.reply_text(message, parse_mode='HTML')
        
    except ValueError:
        await update.message.reply_text("❌ Target harga harus berupa angka")
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        await update.message.reply_text(f"❌ Terjadi kesalahan: {str(e)}")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /list_products"""
    products = load_products()
    
    if not products:
        await update.message.reply_text("📭 Belum ada produk yang dipantau.")
        return
    
    message = "<b>📋 Daftar Produk</b>\n\n"
    
    for product in products:
        current = product.get('current_price', 'N/A')
        target = product.get('target_price', 'N/A')
        
        if isinstance(current, int):
            current = f"Rp{current:,.0f}".replace(',', '.')
        if isinstance(target, int):
            target = f"Rp{target:,.0f}".replace(',', '.')
        
        message += f"""
<b>{product['id']}. {product['name']}</b>
   Platform: {product['platform']}
   Harga Sekarang: {current}
   Target: {target}
   
"""
    
    message += "\n<i>Gunakan /remove_product [nomor] untuk menghapus</i>"
    await update.message.reply_text(message, parse_mode='HTML')

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /remove_product"""
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Format salah!\n"
                "Gunakan: /remove_product [nomor]\n\n"
                "Contoh: /remove_product 1"
            )
            return
        
        product_id = int(context.args[0])
        products = load_products()
        
        products = [p for p in products if p['id'] != product_id]
        save_products(products)
        
        await update.message.reply_text(f"✅ Produk #{product_id} telah dihapus.")
        
    except ValueError:
        await update.message.reply_text("❌ Nomor produk harus berupa angka")
    except Exception as e:
        logger.error(f"Error removing product: {e}")
        await update.message.reply_text(f"❌ Terjadi kesalahan: {str(e)}")

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /check_now - Cek harga semua produk sekarang"""
    products = load_products()
    
    if not products:
        await update.message.reply_text("📭 Belum ada produk untuk dicek.")
        return
    
    await update.message.reply_text("⏳ Sedang cek harga semua produk...")
    
    alert_count = 0
    
    for product in products:
        try:
            current_price = get_current_price(product['platform'], product['url'])
            
            if current_price is None:
                continue
            
            product['current_price'] = current_price
            product['last_checked'] = datetime.now().isoformat()
            
            # Jika harga mencapai target, kirim notifikasi
            if current_price <= product['target_price']:
                price_formatted = f"Rp{current_price:,.0f}".replace(',', '.')
                target_formatted = f"Rp{product['target_price']:,.0f}".replace(',', '.')
                
                message = f"""
🎉 <b>HARGA TARGET TERCAPAI!</b>

📦 Produk: {product['name']}
🏪 Platform: {product['platform']}
💰 Harga Sekarang: <b>{price_formatted}</b>
🎯 Target Harga: {target_formatted}

<a href="{product['url']}">Beli Sekarang</a>
"""
                await send_message(context.application, message)
                alert_count += 1
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error checking product {product['name']}: {e}")
    
    save_products(products)
    
    if alert_count > 0:
        await update.message.reply_text(f"✅ Pengecekan selesai! {alert_count} produk mencapai target harga.")
    else:
        await update.message.reply_text("✅ Pengecekan selesai. Tidak ada produk yang mencapai target harga.")

async def main():
    """Jalankan bot"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_product", add_product))
    application.add_handler(CommandHandler("list_products", list_products))
    application.add_handler(CommandHandler("remove_product", remove_product))
    application.add_handler(CommandHandler("check_now", check_now))
    
    logger.info("Bot started successfully!")
    
    async with application:
        await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
