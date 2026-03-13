# Flash Sale Watcher

CLI Python untuk memantau satu halaman produk Shopee dari URL dan menampilkan harga yang terdeteksi.

Batasan:
- Tidak melakukan login, add-to-cart, atau checkout.
- Tidak mencoba menghindari deteksi, rate limit, atau proteksi platform.
- Untuk halaman produk, script menggabungkan source HTML dan hasil render browser agar peluang menemukan harga lebih besar.

## Kebutuhan

- Python 3.10+
- Package pada `requirements.txt`
- Browser Chromium untuk Playwright

## Cara pakai

1. Install dependency:

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

2. Sesuaikan `config.json`.
3. Jalankan:

```powershell
python flashsale_watcher.py --config config.json
```

Opsi penting:

```powershell
python flashsale_watcher.py --config config.json --interval 10 --timeout 8
```

Mode file lokal:

```powershell
python flashsale_watcher.py --from-file page.txt --page-type flash_sale --product dompet --keyword "flash sale" --keyword "sedang berjalan"
python flashsale_watcher.py --html saved_page.html --page-type flash_sale --product dompet --keyword "flash sale" --keyword "sedang berjalan"
```

## Format config

```json
{
  "interval_seconds": 15,
  "timeout_seconds": 15,
  "warmup_minutes": 15,
  "items": [
    {
      "name": "Produk A",
      "url": "https://shopee.co.id/produk-anda",
      "page_type": "product"
    }
  ]
}
```

Catatan:
- `start_at` opsional. Jika diisi, watcher akan santai dulu lalu masuk mode pemantauan aktif mendekati waktu tersebut.
- Untuk mode `product`, `active_keywords` dan `product_terms` opsional penuh.
- Jika keyword tidak diisi, script akan mencoba mendeteksi harga, sinyal beli, dan marker produk tidak tersedia secara otomatis.
- Tambahkan `--headed` jika Anda ingin melihat browser saat script berjalan.
- Untuk mode file lokal, `--product` bisa diulang beberapa kali dan `--keyword` opsional.

## Test

```powershell
python -m unittest test_detector.py
```
