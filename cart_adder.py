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
        try:
            await qty_selector.wait_for(state="visible", timeout=5000)
            await qty_selector.fill(str(quantity))
            await page.wait_for_timeout(1000)
        except Exception:
            pass

        # Tunggu konfirmasi (toast / notifikasi) Shopee
        success = False
        try:
            # Cari teks yang menunjukkan berhasil ditambahkan ke keranjang
            success_locator = page.locator("text=/berhasil.*(keranjang|ditambahkan)/i")
            await success_locator.wait_for(state="visible", timeout=8000)
            success = True
        except Exception:
            # Mungkin tidak muncul toast, lanjut cek lain atau anggap "mungkin"
            pass

        if success and config.get("auto_checkout", False):
            # Langsung checkout dengan ShopeePay
            try:
                print(f"🛒 {item_name} → Checkout dengan Transfer Bank BCA...")
                await page.goto("https://shopee.co.id/cart", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                # Klik tombol checkout (biasanya ada tombol "Checkout" atau "Bayar")
                checkout_btn = page.get_by_role("button").filter(has_text=re.compile(r"checkout|bayar|beli", re.I))
                await checkout_btn.wait_for(state="visible", timeout=10000)
                await checkout_btn.click()
                await page.wait_for_timeout(3000)

                # Pilih metode pembayaran Transfer Bank
                bank_transfer_option = page.locator("text=/transfer bank|bank transfer/i").first
                await bank_transfer_option.wait_for(state="visible", timeout=10000)
                await bank_transfer_option.click()
                await page.wait_for_timeout(2000)

                # Pilih Bank BCA
                bca_option = page.locator("text=/bca|BCA/i").first
                await bca_option.wait_for(state="visible", timeout=10000)
                await bca_option.click()
                await page.wait_for_timeout(2000)

                # Klik tombol konfirmasi pembayaran
                confirm_btn = page.get_by_role("button").filter(has_text=re.compile(r"bayar|konfirmasi|pay now", re.I))
                await confirm_btn.wait_for(state="visible", timeout=10000)
                await confirm_btn.click()
                await page.wait_for_timeout(5000)

                # Screenshot setelah checkout
                screenshot_path = f"/tmp/checkout_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path, full_page=False)

                message = f"""
💳 FLASH SALE CHECKOUT BERHASIL (Transfer Bank BCA){color_text}
Produk: <b>{item_name}</b>
Harga: {price_text}
Quantity: {quantity}
Link: {url}
✅ Sudah checkout dengan Transfer Bank BCA! Cek rekening BCA untuk detail pembayaran.
                """.strip()
                send_telegram_alert(config, message, screenshot_path)
                print(f"✅ {item_name} → Checkout selesai!")
                return

            except Exception as e:
                print(f"❌ Gagal checkout {item_name}: {str(e)}")
                # Jika gagal checkout, tetap kirim notif add to cart
                pass

        # Screenshot untuk bukti (kirim ke Telegram)
        screenshot_path = f"/tmp/cart_{int(time.time())}.png"  # /tmp aman di server
        await page.screenshot(path=screenshot_path, full_page=False)

        price_text = "harga sesuai range"
        color_text = f" (warna: {selected_color})" if selected_color else ""
        if success:
            message = f"""
🛒 FLASH SALE BERHASIL (Add to Cart){color_text}
Produk: <b>{item_name}</b>
Harga: {price_text}
Quantity: {quantity}
Link: {url}
✅ Sudah ditambahkan ke keranjang!
            """.strip()
        else:
            message = f"""
🛒 FLASH SALE TERDETEKSI (tapi belum pasti masuk ke keranjang){color_text}
Produk: <b>{item_name}</b>
Harga: {price_text}
Quantity: {quantity}
Link: {url}
⚠️ Tidak ditemukan notifikasi "berhasil". Cek manual di keranjang.
            """.strip()

        send_telegram_alert(config, message, screenshot_path)
        print(f"✅ {item_name} → Add to Cart selesai (success={success}) + notif dikirim!")
        
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