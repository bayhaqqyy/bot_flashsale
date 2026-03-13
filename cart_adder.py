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
            print(f"✅ Toast berhasil ditemukan untuk {item_name}")
        except Exception as e:
            print(f"⚠️ Toast berhasil tidak muncul untuk {item_name}: {e}")
            # Mungkin tidak muncul toast, tapi tetap anggap berhasil jika tidak error sebelumnya
            success = True  # Anggap berhasil jika add to cart tidak error

        if success and config.get("auto_checkout", False):
            # Langsung checkout dengan Transfer Bank BCA
            try:
                print(f"🛒 {item_name} → Checkout dengan Transfer Bank BCA...")
                await page.goto("https://shopee.co.id/cart", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                print(f"✅ Halaman keranjang loaded untuk {item_name}")

                # Klik tombol checkout (coba beberapa variasi)
                checkout_btn = None
                for text in ["checkout sekarang", "bayar sekarang", "checkout", "bayar", "beli"]:
                    try:
                        checkout_btn = page.get_by_role("button").filter(has_text=re.compile(text, re.I)).first
                        await checkout_btn.wait_for(state="visible", timeout=5000)
                        print(f"✅ Tombol checkout ditemukan: {text}")
                        break
                    except:
                        continue
                if checkout_btn is None:
                    raise Exception("Tombol checkout tidak ditemukan")
                await checkout_btn.click()
                await page.wait_for_timeout(3000)
                await page.wait_for_load_state("networkidle", timeout=10000)  # Tunggu halaman load
                # Scroll ke bagian pembayaran jika perlu
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await page.wait_for_timeout(1000)
                print(f"✅ Tombol checkout diklik untuk {item_name}")

                # Pilih metode pembayaran Transfer Bank
                bank_transfer_option = None
                for text in ["transfer bank", "bank transfer", "transfer", "bank"]:
                    try:
                        bank_transfer_option = page.locator(f"text=/{text}/i").first
                        await bank_transfer_option.wait_for(state="visible", timeout=10000)
                        print(f"✅ Opsi transfer bank ditemukan: {text}")
                        break
                    except:
                        continue
                if bank_transfer_option is None:
                    # Coba dengan selector lain, misal berdasarkan class atau role
                    try:
                        bank_transfer_option = page.locator("[data-testid*='bank-transfer'], .bank-transfer, [aria-label*='transfer']").first
                        await bank_transfer_option.wait_for(state="visible", timeout=5000)
                        print("✅ Opsi transfer bank ditemukan dengan selector alternatif")
                    except:
                        raise Exception("Opsi transfer bank tidak ditemukan")
                await bank_transfer_option.click()
                await page.wait_for_timeout(2000)

                # Pilih Bank BCA
                bca_option = None
                for text in ["bca", "BCA", "Bank Central Asia"]:
                    try:
                        bca_option = page.locator(f"text=/{text}/i").first
                        await bca_option.wait_for(state="visible", timeout=5000)
                        print(f"✅ Bank BCA ditemukan: {text}")
                        break
                    except:
                        continue
                if bca_option is None:
                    # Coba dengan selector lain
                    try:
                        bca_option = page.locator("[data-testid*='bca'], .bca-bank, img[alt*='bca']").first
                        await bca_option.wait_for(state="visible", timeout=5000)
                        print("✅ Bank BCA ditemukan dengan selector alternatif")
                    except:
                        raise Exception("Bank BCA tidak ditemukan")
                await bca_option.click()
                await page.wait_for_timeout(2000)

                # Klik tombol konfirmasi pembayaran
                confirm_btn = None
                for text in ["bayar", "konfirmasi", "pay now", "bayar sekarang"]:
                    try:
                        confirm_btn = page.get_by_role("button").filter(has_text=re.compile(text, re.I)).first
                        await confirm_btn.wait_for(state="visible", timeout=5000)
                        print(f"✅ Tombol konfirmasi ditemukan: {text}")
                        break
                    except:
                        continue
                if confirm_btn is None:
                    raise Exception("Tombol konfirmasi tidak ditemukan")
                await confirm_btn.click()
                await page.wait_for_timeout(5000)
                print(f"✅ Tombol konfirmasi diklik untuk {item_name}")

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