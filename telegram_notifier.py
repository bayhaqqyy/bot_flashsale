import requests

def send_telegram_alert(config: dict, message: str, screenshot_path: str = None):
    token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
    
    if screenshot_path:
        url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
        with open(screenshot_path, "rb") as f:
            requests.post(url_photo, data={"chat_id": chat_id}, files={"photo": f})