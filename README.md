# Flash Sale Watcher

CLI Python untuk memantau halaman produk Shopee dan memberi alert saat indikator flash sale mulai muncul.

Batasan:
- Tidak melakukan login, add-to-cart, atau checkout.
- Tidak mencoba menghindari deteksi, rate limit, atau proteksi platform.
- Deteksi berbasis konten halaman/keyword, jadi mungkin perlu disetel ulang jika markup Shopee berubah.

## Kebutuhan

- Python 3.10+

## Cara pakai

1. Salin `config.example.json` menjadi `config.json`.
2. Isi daftar produk yang ingin dipantau.
3. Jalankan:

```powershell
python flashsale_watcher.py --config config.json
```

Opsi penting:

```powershell
python flashsale_watcher.py --config config.json --interval 10 --timeout 8
```

## Format config

```json
{
  "interval_seconds": 15,
  "timeout_seconds": 10,
  "warmup_minutes": 15,
  "items": [
    {
      "name": "Produk A",
      "url": "https://shopee.co.id/...",
      "start_at": "2026-03-11T20:00:00+07:00",
      "active_keywords": [
        "flash sale",
        "berlangsung"
      ]
    }
  ]
}
```

Catatan:
- `start_at` opsional. Jika diisi, watcher akan santai dulu lalu masuk mode pemantauan aktif mendekati waktu tersebut.
- `active_keywords` opsional. Jika diisi, item dianggap aktif bila semua keyword ini muncul pada HTML halaman.

## Test

```powershell
python -m unittest test_detector.py
```
