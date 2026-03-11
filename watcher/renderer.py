class BrowserRenderer:
    def __init__(self, timeout_seconds: int, headless: bool = True) -> None:
        self.timeout_ms = timeout_seconds * 1000
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

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
        context = self._browser.new_context(
            locale="id-ID",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        self._page = context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._page is not None:
            self._page.context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def fetch_text(self, url: str) -> str:
        if self._page is None:
            raise RuntimeError("BrowserRenderer belum diinisialisasi.")

        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_timeout(3000)
        body = self._page.locator("body")
        return body.inner_text()
