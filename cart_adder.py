# cart_adder.py
import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from telegram_notifier import send_telegram_alert

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page
else:
    BrowserContext = Any
    Page = Any


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)

ADD_TO_CART_PATTERN = re.compile(r"masukkan ke keranjang|add to cart|keranjang", re.I)
BUY_NOW_PATTERN = re.compile(r"beli sekarang|buy now", re.I)
SUCCESS_PATTERN = re.compile(r"berhasil.*(keranjang|ditambahkan)", re.I)


def _clean_cookie(raw: dict[str, Any]) -> dict[str, Any]:
    cookie = {
        "name": raw["name"],
        "value": raw["value"],
        "domain": raw["domain"],
        "path": raw.get("path", "/"),
    }
    expires = raw.get("expires", raw.get("expirationDate"))
    if expires is not None:
        cookie["expires"] = int(expires)
    if "httpOnly" in raw:
        cookie["httpOnly"] = bool(raw["httpOnly"])
    if "secure" in raw:
        cookie["secure"] = bool(raw["secure"])

    same_site = raw.get("sameSite")
    if same_site:
        same_site = str(same_site).strip().lower()
        cookie["sameSite"] = same_site.capitalize() if same_site in {"strict", "lax", "none"} else "Lax"
    return cookie


def load_auth_state(path: str | Path) -> dict[str, Any]:
    """Load either Playwright storage_state JSON or exported browser cookies JSON."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "cookies" in payload:
        return payload
    if isinstance(payload, list):
        return {"cookies": [_clean_cookie(cookie) for cookie in payload], "origins": []}
    raise ValueError("Format cookie tidak dikenali. Pakai storage_state Playwright atau list cookies browser.")


async def create_cli_context(
    *,
    auth_path: str,
    headless: bool,
    fast: bool,
) -> tuple[Any, Any, BrowserContext]:
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1280,900",
        ],
    )
    context = await browser.new_context(
        storage_state=load_auth_state(auth_path),
        viewport={"width": 1280, "height": 900},
        user_agent=DEFAULT_USER_AGENT,
        locale="id-ID",
        timezone_id="Asia/Jakarta",
        ignore_https_errors=True,
    )
    if fast:
        await context.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_()
            ),
        )
    return pw, browser, context


async def _try_select_color(page: Page) -> str | None:
    try:
        color_btn = page.get_by_role("button").filter(has_text=re.compile(r"\b(hitam|black)\b", re.I))
        if await color_btn.count() > 0:
            await color_btn.first.click(timeout=800)
            return "Hitam"
    except Exception:
        pass
    return None


async def _fast_click(locator: Any, *, timeout: int, prefer_dom: bool = False) -> None:
    """Click with fallbacks for animated buttons that never become stable fast enough."""
    if prefer_dom:
        try:
            await locator.evaluate(
                """element => {
                    element.scrollIntoView({block: 'center', inline: 'center'});
                    element.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                    element.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                    element.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    element.click();
                }""",
                timeout=timeout,
            )
            return
        except Exception as dom_error:
            first_error = dom_error
    else:
        first_error = None

    try:
        await locator.click(timeout=timeout)
        return
    except Exception as click_error:
        if first_error is None:
            first_error = click_error
        try:
            await locator.click(timeout=500, force=True)
            return
        except Exception as force_error:
            try:
                handle = await locator.element_handle(timeout=500)
                if handle is None:
                    raise first_error
                await handle.evaluate("element => element.click()")
                return
            except Exception as handle_error:
                raise RuntimeError(
                    "Semua metode klik gagal: "
                    f"dom/click={first_error}; force={force_error}; handle={handle_error}"
                ) from first_error


async def _click_button_by_text_js(page: Page, labels: list[str], *, timeout_ms: int) -> bool:
    deadline = time.perf_counter() + (timeout_ms / 1000)
    labels = [label.lower() for label in labels]
    while time.perf_counter() < deadline:
        clicked = await page.evaluate(
            """labels => {
                const candidates = Array.from(document.querySelectorAll('button, [role="button"]'));
                const isVisible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                };
                const target = candidates.find(element => {
                    const text = (element.innerText || element.textContent || '').trim().toLowerCase();
                    const disabled = element.disabled || element.getAttribute('aria-disabled') === 'true';
                    return !disabled && isVisible(element) && labels.some(label => text.includes(label));
                });
                if (!target) {
                    return false;
                }
                target.scrollIntoView({block: 'center', inline: 'center'});
                target.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true, view: window}));
                target.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                target.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, cancelable: true, view: window}));
                target.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                target.click();
                return true;
            }""",
            labels,
        )
        if clicked:
            return True
        await page.wait_for_timeout(100)
    return False


async def _button_rect_by_text(page: Page, labels: list[str], *, timeout_ms: int) -> dict[str, Any] | None:
    deadline = time.perf_counter() + (timeout_ms / 1000)
    labels = [label.lower() for label in labels]
    while time.perf_counter() < deadline:
        rect = await page.evaluate(
            """labels => {
                const candidates = Array.from(document.querySelectorAll('button, [role="button"]'));
                const isVisible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                };
                const scored = candidates
                    .map(element => {
                        const text = (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const disabled = element.disabled || element.getAttribute('aria-disabled') === 'true';
                        if (disabled || !isVisible(element)) return null;
                        const index = labels.findIndex(label => text.includes(label));
                        if (index === -1) return null;
                        return {element, text, score: index};
                    })
                    .filter(Boolean)
                    .sort((a, b) => a.score - b.score || b.text.length - a.text.length);

                if (!scored.length) return null;

                const target = scored[0].element;
                target.scrollIntoView({block: 'center', inline: 'center'});
                const box = target.getBoundingClientRect();
                return {
                    x: box.left + box.width / 2,
                    y: box.top + box.height / 2,
                    width: box.width,
                    height: box.height,
                    text: scored[0].text
                };
            }""",
            labels,
        )
        if rect:
            return rect
        await page.wait_for_timeout(100)
    return None


async def _click_button_by_text_mouse(page: Page, labels: list[str], *, timeout_ms: int) -> dict[str, Any]:
    rect = await _button_rect_by_text(page, labels, timeout_ms=timeout_ms)
    if rect is None:
        raise RuntimeError("Tombol add-to-cart tidak ditemukan oleh scan DOM cepat.")

    x = float(rect["x"])
    y = float(rect["y"])
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.wait_for_timeout(35)
    await page.mouse.up()
    return rect


async def _wait_add_to_cart_result(page: Page, *, timeout_ms: int) -> tuple[bool, str]:
    deadline = time.perf_counter() + (timeout_ms / 1000)
    success_markers = [
        "berhasil ditambahkan",
        "berhasil masuk",
        "ditambahkan ke keranjang",
        "added to cart",
    ]
    failure_markers = [
        "pilih variasi",
        "pilih opsi",
        "silakan pilih",
        "stok habis",
        "masuk untuk",
        "login",
    ]
    while time.perf_counter() < deadline:
        body_text = await page.locator("body").inner_text(timeout=700)
        normalized = re.sub(r"\s+", " ", body_text).lower()
        for marker in success_markers:
            if marker in normalized:
                return True, marker
        for marker in failure_markers:
            if marker in normalized:
                return False, marker
        await page.wait_for_timeout(150)
    return False, "tidak ada konfirmasi berhasil dari halaman"


async def _wait_checkout_result(page: Page, *, timeout_ms: int) -> tuple[bool, str]:
    deadline = time.perf_counter() + (timeout_ms / 1000)
    checkout_markers = [
        "checkout",
        "ringkasan pesanan",
        "alamat pengiriman",
        "metode pembayaran",
        "buat pesanan",
        "place order",
    ]
    failure_markers = [
        "pilih variasi",
        "pilih opsi",
        "silakan pilih",
        "stok habis",
        "masuk untuk",
        "login",
    ]
    while time.perf_counter() < deadline:
        current_url = page.url.lower()
        if "checkout" in current_url:
            return True, "halaman checkout terbuka"

        body_text = await page.locator("body").inner_text(timeout=700)
        normalized = re.sub(r"\s+", " ", body_text).lower()
        for marker in checkout_markers:
            if marker in normalized:
                return True, marker
        for marker in failure_markers:
            if marker in normalized:
                return False, marker
        await page.wait_for_timeout(150)
    return False, "tidak ada konfirmasi halaman checkout"


async def add_to_cart(
    page: Page,
    url: str,
    quantity: int,
    config: dict,
    item_name: str,
    *,
    fast: bool | None = None,
    direct_checkout: bool = False,
) -> bool:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    fast = config.get("fast_cart", False) if fast is None else fast
    started_at = time.perf_counter()
    success = False
    selected_color = None

    try:
        page.set_default_timeout(1500 if fast else 10000)
        await page.goto(url, wait_until="domcontentloaded", timeout=8000 if fast else 45000)

        selected_color = await _try_select_color(page)

        if direct_checkout and fast:
            clicked_button = await _click_button_by_text_mouse(
                page,
                ["beli sekarang", "buy now"],
                timeout_ms=2500,
            )
            print(f"[CLICK] Tombol: {clicked_button['text']}")
        elif direct_checkout:
            buy_btn = page.get_by_role("button").filter(has_text=BUY_NOW_PATTERN).first
            await buy_btn.wait_for(state="visible", timeout=10000)
            await _fast_click(buy_btn, timeout=15000)
        elif fast:
            clicked_button = await _click_button_by_text_mouse(
                page,
                ["masukkan ke keranjang", "masukkan keranjang", "add to cart"],
                timeout_ms=2500,
            )
            print(f"[CLICK] Tombol: {clicked_button['text']}")
        else:
            add_btn = page.get_by_role("button").filter(has_text=ADD_TO_CART_PATTERN).first
            await add_btn.wait_for(state="visible", timeout=10000)
            await _fast_click(add_btn, timeout=15000)

        if fast:
            await page.wait_for_timeout(150)

        qty_selector = page.locator("input[type='number'], [aria-label*='jumlah'], [placeholder*='jumlah']").first
        try:
            await qty_selector.wait_for(state="visible", timeout=500 if fast else 5000)
            await qty_selector.fill(str(quantity), timeout=500 if fast else 3000)
        except PlaywrightTimeoutError:
            pass

        if direct_checkout:
            success, result_reason = await _wait_checkout_result(page, timeout_ms=2500 if fast else 10000)
        else:
            success, result_reason = await _wait_add_to_cart_result(page, timeout_ms=1800 if fast else 8000)
        if not success:
            target = "checkout" if direct_checkout else "masuk cart"
            raise RuntimeError(f"Klik terkirim, tapi belum terkonfirmasi {target}: {result_reason}")

        if config.get("auto_checkout", False):
            print("Auto checkout final tidak dijalankan. Script berhenti sebelum tombol pembayaran/pesanan.")

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        action_text = "checkout page" if direct_checkout else "add-to-cart"
        print(f"[OK] {item_name} {action_text} selesai dalam {elapsed_ms} ms")

        if config.get("telegram_enabled", True) and not fast:
            screenshot_path = f"/tmp/cart_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            color_text = f" (warna: {selected_color})" if selected_color else ""
            message = (
                f"FLASH SALE BERHASIL (Add to Cart){color_text}\n"
                f"Produk: <b>{item_name}</b>\n"
                f"Quantity: {quantity}\n"
                f"Link: {url}\n"
                "Sudah ditambahkan ke keranjang."
            )
            send_telegram_alert(config, message, screenshot_path)
        return success

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        print(f"[ERR] Gagal add-to-cart {item_name} setelah {elapsed_ms} ms: {exc}")
        if config.get("telegram_enabled", True) and not fast:
            try:
                screenshot_path = f"/tmp/cart_err_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path, full_page=False)
                send_telegram_alert(config, f"Gagal add-to-cart <b>{item_name}</b>: {exc}", screenshot_path)
            except Exception:
                pass
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add produk Shopee ke cart dari CLI memakai cookie/storage-state.")
    parser.add_argument("--url", required=True, help="URL produk.")
    parser.add_argument("--name", default="Produk", help="Nama produk untuk log.")
    parser.add_argument("--quantity", type=int, default=1, help="Jumlah item.")
    parser.add_argument("--auth", default="cookies/cookies.json", help="Path cookies JSON atau storage_state JSON.")
    parser.add_argument("--config", default=None, help="Config JSON opsional untuk Telegram/setting lain.")
    parser.add_argument("--headed", action="store_true", help="Tampilkan browser.")
    parser.add_argument("--fast", action="store_true", help="Mode cepat: timeout pendek, tanpa screenshot/Telegram.")
    parser.add_argument(
        "--checkout",
        action="store_true",
        help="Klik Beli Sekarang dan berhenti di halaman checkout, tanpa menekan tombol final pesanan/bayar.",
    )
    return parser.parse_args()


def load_optional_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def run_cli(args: argparse.Namespace) -> int:
    config = load_optional_config(args.config)
    config.setdefault("telegram_enabled", False)
    pw, browser, context = await create_cli_context(
        auth_path=args.auth,
        headless=not args.headed,
        fast=args.fast,
    )
    try:
        page = await context.new_page()
        try:
            ok = await add_to_cart(
                page,
                args.url,
                args.quantity,
                config,
                args.name,
                fast=args.fast,
                direct_checkout=args.checkout,
            )
            return 0 if ok else 1
        finally:
            await page.close()
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


def main() -> int:
    return asyncio.run(run_cli(parse_args()))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDihentikan oleh user.")
        raise SystemExit(130)
