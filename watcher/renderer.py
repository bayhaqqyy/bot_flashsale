class BrowserRenderer:
    def __init__(self, timeout_seconds: int, headless: bool = True) -> None:
        self.timeout_ms = timeout_seconds * 1000
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None
        self._context = None

    def __enter__(self) -> "BrowserRenderer":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright belum terpasang. Install dulu dengan "
                "'pip install -r requirements.txt' lalu 'python -m playwright install chromium'."
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            locale="id-ID",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for closer in (self._safe_close_context, self._safe_close_browser, self._safe_stop_playwright):
            closer()

    def fetch_text(self, url: str) -> str:
        if self._page is None:
            raise RuntimeError("BrowserRenderer belum diinisialisasi.")

        self._page.goto(url, wait_until="domcontentloaded")
        try:
            self._page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except Exception:
            pass
        self._page.wait_for_timeout(2000)
        self._scroll_page()
        body = self._page.locator("body")
        return body.inner_text()

    def _scroll_page(self) -> None:
        if self._page is None:
            return

        previous_height = -1
        stable_rounds = 0
        for _ in range(12):
            self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self._page.wait_for_timeout(1200)
            current_height = self._page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if stable_rounds >= 2:
                break
            previous_height = current_height

        self._page.evaluate("window.scrollTo(0, 0)")
        self._page.wait_for_timeout(500)

    def _safe_close_context(self) -> None:
        if self._context is None:
            return
        try:
            self._context.close()
        except Exception:
            pass
        finally:
            self._context = None
            self._page = None

    def _safe_close_browser(self) -> None:
        if self._browser is None:
            return
        try:
            self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None

    def _safe_stop_playwright(self) -> None:
        if self._playwright is None:
            return
        try:
            self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None
