import random


class BrowserRenderer:
    def __init__(self, timeout_seconds: int, headless: bool = True, context=None) -> None:
        self.timeout_ms = timeout_seconds * 1000
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None
        self._context = context

    async def __aenter__(self) -> "BrowserRenderer":
        if self._context is None:
            from browser import get_logged_in_browser
            self._pw, self._browser, self._context, self._page = await get_logged_in_browser(headless=self.headless)
        else:
            self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Close page
        if self._page:
            await self._page.close()
            self._page = None
        # If context was provided externally, don't close it
        if self._context is not None and self._pw is None:  # meaning context was provided
            return
        # Else, close everything
        for closer in (self._safe_close_context, self._safe_close_browser, self._safe_stop_pw):
            await closer()

    async def fetch_text(self, url: str) -> str:
        if self._page is None:
            raise RuntimeError("BrowserRenderer belum diinisialisasi.")

        await self._page.goto(url, wait_until="domcontentloaded")
        try:
            await self._page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except Exception:
            pass

        # Tambahkan delay acak agar tidak terlihat bot
        await self._page.wait_for_timeout(int(random.uniform(800, 2000)))

        # Scroll dan gerakan mouse mirip manusia
        await self._humanize_interaction()

        body = self._page.locator("body")
        return await body.inner_text()

    async def _scroll_page(self) -> None:
        if self._page is None:
            return

        previous_height = -1
        stable_rounds = 0
        for _ in range(12):
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._page.wait_for_timeout(int(random.uniform(800, 1400)))
            current_height = await self._page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if stable_rounds >= 2:
                break
            previous_height = current_height

        await self._page.evaluate("window.scrollTo(0, 0)")
        await self._page.wait_for_timeout(int(random.uniform(400, 900)))

    async def _humanize_interaction(self) -> None:
        """Lakukan scroll / mouse movement secara acak biar mirip pengguna manusia."""
        if self._page is None:
            return

        # Scroll sedikit acak
        await self._scroll_page()

        # Gerakan mouse acak di viewport
        try:
            width = await self._page.evaluate("window.innerWidth")
            height = await self._page.evaluate("window.innerHeight")
            for _ in range(random.randint(2, 5)):
                x = random.randint(int(width * 0.1), int(width * 0.9))
                y = random.randint(int(height * 0.1), int(height * 0.9))
                await self._page.mouse.move(x, y, steps=random.randint(10, 25))
                await self._page.wait_for_timeout(int(random.uniform(200, 700)))
        except Exception:
            pass

    async def _safe_close_context(self) -> None:
        if self._context is None:
            return
        try:
            await self._context.close()
        except Exception:
            pass
        finally:
            self._context = None
            self._page = None

    async def _safe_close_browser(self) -> None:
        if self._browser is None:
            return
        try:
            await self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None

    async def _safe_stop_pw(self) -> None:
        if self._pw is None:
            return
        try:
            await self._pw.stop()
        except Exception:
            pass
        finally:
            self._pw = None
