import unittest

from watcher.detector import DetectionInput, detect_flash_sale


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


if __name__ == "__main__":
    unittest.main()
