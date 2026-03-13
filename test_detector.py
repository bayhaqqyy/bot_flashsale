import unittest

from watcher.detector import DetectionInput, detect_flash_sale, extract_prices
from flashsale_watcher import html_to_text


class DetectorTests(unittest.TestCase):
    def test_flash_sale_page_detects_active_item(self) -> None:
        text = "FLASH SALE sedang berjalan. promo dompet pria original diskon besar."
        result = detect_flash_sale(
            DetectionInput(
                page_text=text,
                page_type="flash_sale",
                active_keywords=["flash sale", "sedang berjalan"],
                product_terms=["dompet"],
                item_name="Dompet pria PL0045",
            )
        )
        self.assertTrue(result.is_active)

    def test_flash_sale_page_needs_status_and_product(self) -> None:
        text = "FLASH SALE akan datang. kategori fashion."
        result = detect_flash_sale(
            DetectionInput(
                page_text=text,
                page_type="flash_sale",
                active_keywords=["flash sale", "sedang berjalan"],
                product_terms=["dompet"],
            )
        )
        self.assertFalse(result.is_active)

    def test_product_page_keywords_still_work(self) -> None:
        text = "Flash sale berlangsung. Beli sekarang."
        result = detect_flash_sale(
            DetectionInput(
                page_text=text,
                page_type="product",
                active_keywords=["flash sale", "beli sekarang"],
            )
        )
        self.assertTrue(result.is_active)
        self.assertEqual(result.availability, "available")

    def test_product_page_without_keywords_can_use_price_and_buy_signal(self) -> None:
        text = "Dompet pria original. Rp12.000. Beli sekarang."
        result = detect_flash_sale(
            DetectionInput(
                page_text=text,
                page_type="product",
            )
        )
        self.assertTrue(result.is_active)
        self.assertEqual(result.prices, ["Rp12.000"])

    def test_product_page_marks_unavailable(self) -> None:
        text = "Dompet pria. Stok habis. Rp12.000."
        result = detect_flash_sale(
            DetectionInput(
                page_text=text,
                page_type="product",
            )
        )
        self.assertFalse(result.is_active)
        self.assertEqual(result.availability, "unavailable")

    def test_html_to_text_extracts_content(self) -> None:
        raw_html = "<html><body><div>Flash Sale sedang berjalan</div><p>Dompet pria</p></body></html>"
        text = html_to_text(raw_html)
        self.assertIn("Flash Sale sedang berjalan", text)
        self.assertIn("Dompet pria", text)

    def test_extract_prices_finds_rupiah_values(self) -> None:
        prices = extract_prices("Harga promo Rp12.000 lalu Rp9.500 untuk dompet.")
        self.assertEqual(prices, ["Rp12.000", "Rp9.500"])


if __name__ == "__main__":
    unittest.main()
