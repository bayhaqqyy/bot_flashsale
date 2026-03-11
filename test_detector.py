import unittest

from watcher.detector import detect_flash_sale


class DetectorTests(unittest.TestCase):
    def test_custom_keywords_activate_item(self) -> None:
        html = "<html>Flash Sale lagi berlangsung. Beli Sekarang.</html>"
        result = detect_flash_sale(html, ["flash sale", "beli sekarang"])
        self.assertTrue(result.is_active)

    def test_live_combination_is_detected(self) -> None:
        html = "<html><body>Flash Sale sedang berlangsung, stok terbatas.</body></html>"
        result = detect_flash_sale(html)
        self.assertTrue(result.is_active)

    def test_teaser_only_is_not_detected(self) -> None:
        html = "<html><body>Flash Sale akan datang besok.</body></html>"
        result = detect_flash_sale(html)
        self.assertFalse(result.is_active)


if __name__ == "__main__":
    unittest.main()
