# cart_adder.py
import re
import time
from telegram_notifier import send_telegram_alert

async def add_to_cart(page, url: str, quantity: int, config: dict, item_name: str):
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(3000)
        
        # Pilih opsi warna "Hitam" jika ada (biasanya varian warna)
        selected_color = None
        try:
            color_btn = page.get_by_role("button").filter(has_text=re.compile(r"\b(hitam|black)\b", re.I))
            if await color_btn.count() > 0:
                await color_btn.first.click()
                await page.wait_for_timeout(1500)
                selected_color = "Hitam"
        except Exception:
            pass

        # Cari tombol "Masukkan ke Keranjang" (text match, case insensitive)
        add_btn = page.get_by_role("button").filter(has_text=re.compile(r"masukkan ke keranjang|add to cart|keranjang", re.I))
        try:
            await add_btn.wait_for(state="visible", timeout=10000)
        except Exception:
            raise Exception("Tombol add to cart tidak ditemukan (atau tidak terlihat)")

        await add_btn.click(timeout=15000)
        await page.wait_for_timeout(4000)

        # Kalau muncul popup quantity, isi
        qty_selector = page.locator("input[type='number'], [aria-label*='jumlah'], [placeholder*='jumlah']")
        if await qty_selector.is_visible(timeout=5000):
            await qty_selector.fill(str(quantity))
            await page.wait_for_timeout(1000)
        
        # Screenshot untuk bukti (kirim ke Telegram)
        screenshot_path = f"/tmp/cart_{int(time.time())}.png"  # /tmp aman di server
        await page.screenshot(path=screenshot_path, full_page=False)
        
        price_text = "harga sesuai range"
        color_text = f" (warna: {selected_color})" if selected_color else ""
        message = f"""
🛒 FLASH SALE BERHASIL (Add to Cart){color_text}
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
        # Screenshot on failure (bisa bantu debugging)
        try:
            screenshot_path = f"/tmp/cart_err_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            send_telegram_alert(
                config,
                f"⚠️ Gagal add to cart <b>{item_name}</b>: {e}\n(Lihat screenshot)",
                screenshot_path,
            )
        except Exception:
            pass
        # Optional: kirim error ke Telegram juga