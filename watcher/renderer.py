class BrowserRenderer:
    def __init__(self, timeout_seconds: int, headless: bool = True) -> None:
        self.timeout_ms = timeout_seconds * 1000
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None
        self._context = None

    def __enter__(self) -> "BrowserRenderer":
        from browser import get_logged_in_browser

        self._pw, self._browser, self._context, self._page = get_logged_in_browser(headless=self.headless)
        self._page.set_default_timeout(self.timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for closer in (self._safe_close_context, self._safe_close_browser, self._safe_stop_pw):
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

    def _safe_stop_pw(self) -> None:
        if self._pw is None:
            return
        try:
            self._pw.stop()
        except Exception:
            pass
        finally:
            self._pw = None
