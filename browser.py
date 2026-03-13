# browser.py - versi upgraded untuk bypass interstitial Shopee
from playwright.async_api import async_playwright
import json
import asyncio

async def get_logged_in_browser(headless=True):
    print("Memulai browser headless untuk Shopee...")
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-infobars',
            '--window-size=1280,800',
            '--disable-blink-features=AutomationControlled',  # kurangi deteksi bot
        ]
    )
    
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        locale='id-ID',
        timezone_id='Asia/Jakarta',
        ignore_https_errors=True,
        java_script_enabled=True,
        # Tambah ini biar lebih mirip manusia
        permissions=['geolocation'],
        extra_http_headers={
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
        }
    )
    
    # Load & fix cookies
    try:
        with open("cookies/cookies.json", "r", encoding="utf-8") as f:
            raw_cookies = json.load(f)
        
        clean_cookies = []
        for c in raw_cookies:
            clean = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
            }
            if "expirationDate" in c:
                clean["expires"] = int(c["expirationDate"])
            if "httpOnly" in c:
                clean["httpOnly"] = c["httpOnly"]
            if "secure" in c:
                clean["secure"] = c["secure"]
            
            # Fix sameSite (Playwright hanya terima Strict|Lax|None)
            samesite = c.get("sameSite")
            if samesite:
                lower = str(samesite).lower()
                if lower in ['strict', 'lax', 'none']:
                    clean["sameSite"] = lower.capitalize()
                else:
                    clean["sameSite"] = "Lax"  # default aman
            else:
                clean["sameSite"] = "Lax"
            
            clean_cookies.append(clean)
        
        await context.add_cookies(clean_cookies)
        print("✅ Cookies berhasil dimuat dan difix")
    except Exception as e:
        print(f"❌ Gagal load cookies: {str(e)}")
        raise
    
    page = await context.new_page()
    
    # Bypass automation detection dasar
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        window.chrome = { runtime: {} };
    """)
    
    # Buka halaman utama dulu untuk stabilkan session
    print("Stabilisasi session di halaman utama...")
    await page.goto("https://shopee.co.id", timeout=60000)
    await page.wait_for_load_state("networkidle", timeout=30000)
    await asyncio.sleep(3)
    
    # Tutup popup umum Shopee (lewati promo, notifikasi, dll)
    popup_selectors = [
        "button:has-text('Tutup')",
        "button:has-text('Lewati')",
        "[aria-label*='close']",
        ".shopee-popup__close-btn",
        ".close-icon",
        "div[role='dialog'] button"
    ]
    for sel in popup_selectors:
        try:
            if await page.locator(sel).count() > 0:
                await page.locator(sel).first.click(timeout=5000)
                print(f"Popup ditutup: {sel}")
                await asyncio.sleep(1)
        except:
            pass
    
    # Cek status login (kompatibel versi lama)
    print("Cek status login...")
    is_logged_in = True
    try:
        await page.wait_for_selector("button:has-text('Masuk')", timeout=8000)
        is_logged_in = False
    except:
        pass
    
    if "login" in page.url.lower() or not is_logged_in:
        print("⚠️ Masih terdeteksi login wall di halaman utama!")
        await page.screenshot(path="/tmp/login_check_fail.png")
        print("Screenshot disimpan di /tmp/login_check_fail.png")
    else:
        print("✅ Login Shopee berhasil di headless mode!")
    
    # Return dengan pw supaya bisa close nanti
    return pw, browser, context, page


async def fetch_page_html(url: str, timeout_seconds: int = 15, headless: bool = True) -> str:
    """Fetch HTML dari URL menggunakan browser yang sudah login."""
    pw, browser, context, page = await get_logged_in_browser(headless=headless)
    try:
        await page.goto(url, timeout=timeout_seconds * 1000)
        await page.wait_for_load_state("networkidle", timeout=timeout_seconds * 1000)
        html_content = await page.content()
        return html_content
    finally:
        await context.close()
        await browser.close()
        await pw.stop()