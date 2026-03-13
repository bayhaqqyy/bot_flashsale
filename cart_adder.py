# cart_adder.py
import re
import time
from telegram_notifier import send_telegram_alert

def add_to_cart(page, url: str, quantity: int, config: dict, item_name: str):
    try:
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)
        
        # Cari tombol "Masukkan ke Keranjang" (text match, case insensitive)
        add_btn = page.get_by_role("button").filter(has_text=re.compile(r"masukkan ke keranjang|add to cart|keranjang", re.I))
        if not add_btn.is_visible(timeout=10000):
            raise Exception("Tombol add to cart tidak ditemukan")
        
        add_btn.click(timeout=15000)
        page.wait_for_timeout(4000)
        
        # Kalau muncul popup quantity, isi
        qty_selector = page.locator("input[type='number'], [aria-label*='jumlah'], [placeholder*='jumlah']")
        if qty_selector.is_visible(timeout=5000):
            qty_selector.fill(str(quantity))
            page.wait_for_timeout(1000)
        
        # Screenshot untuk bukti (kirim ke Telegram)
        screenshot_path = f"/tmp/cart_{int(time.time())}.png"  # /tmp aman di server
        page.screenshot(path=screenshot_path, full_page=False)
        
        price_text = "harga sesuai range"
        message = f"""
🛒 FLASH SALE BERHASIL (Add to Cart)
Produk: <b>{item_name}</b>
Harga: {price_text}
Quantity: {quantity}
Link: {url}
✅ Sudah ditambahkan ke keranjang!
        """.strip()
        
        send_telegram_alert(config, message, screenshot_path)
        print(f"✅ {item_name} → Add to Cart sukses + notif dikirim!")
        
    except Exception as e:
        print(f"❌ Gagal add to cart {item_name}: {str(e)}")
        # Optional: kirim error ke Telegram juga