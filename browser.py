# browser.py
from playwright.sync_api import sync_playwright
import json

def get_logged_in_browser(headless=True):  # default True untuk server
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=headless,
        args=[
            '--no-sandbox',               # WAJIB di server (Linux)
            '--disable-setuid-sandbox',   # WAJIB
            '--disable-dev-shm-usage',    # Hindari crash memory di container
            '--disable-gpu',              # Tidak perlu GPU di server
            '--disable-infobars',
            '--window-size=1280,800',
        ]
    )
    
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        locale='id-ID',
        timezone_id='Asia/Jakarta',
        ignore_https_errors=True,  # kadang Shopee punya cert issue
    )
    
    # Load cookies kamu
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
        if "sameSite" in c and c["sameSite"]:
            clean["sameSite"] = c["sameSite"]
        
        clean_cookies.append(clean)
    
    context.add_cookies(clean_cookies)
    
    page = context.new_page()
    
    # Test login cepat (opsional, tapi bagus buat debug)
    page.goto("https://shopee.co.id", timeout=45000)
    page.wait_for_timeout(2000)
    
    if "login" in page.url or page.locator("button:has-text('Masuk')").is_visible(timeout=5000):
        print("⚠️ Login gagal / cookie kadaluarsa!")
    else:
        print("✅ Login Shopee berhasil di headless mode!")
    
    return pw, browser, context, page  # return pw juga biar bisa stop nanti