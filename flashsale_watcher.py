import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from watcher.detector import detect_flash_sale


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}


@dataclass
class WatchItem:
    name: str
    url: str
    start_at: datetime | None = None
    active_keywords: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pantau halaman produk Shopee sampai flash sale aktif."
    )
    parser.add_argument("--config", default="config.json", help="Path file config JSON.")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override interval polling dalam detik.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override timeout HTTP dalam detik.",
    )
    return parser.parse_args()


def load_config(path: str) -> tuple[int, int, int, list[WatchItem]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    interval = int(payload.get("interval_seconds", 15))
    timeout = int(payload.get("timeout_seconds", 10))
    warmup = int(payload.get("warmup_minutes", 15))
    items = [parse_item(item) for item in payload.get("items", [])]
    if not items:
        raise ValueError("Config tidak memiliki item untuk dipantau.")
    return interval, timeout, warmup, items


def parse_item(payload: dict) -> WatchItem:
    name = payload["name"]
    url = payload["url"]
    start_at_raw = payload.get("start_at")
    start_at = None
    if start_at_raw:
        start_at = datetime.fromisoformat(start_at_raw)
        if start_at.tzinfo is None:
            raise ValueError(f"start_at untuk '{name}' harus menyertakan timezone.")

    active_keywords = [keyword.strip().lower() for keyword in payload.get("active_keywords", [])]
    return WatchItem(name=name, url=url, start_at=start_at, active_keywords=active_keywords)


def fetch_html(url: str, timeout_seconds: int) -> str:
    request = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw_body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
        return raw_body.decode(encoding, errors="ignore")


def normalized_now(reference: datetime | None = None) -> datetime:
    current = reference or datetime.now(timezone.utc).astimezone()
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current


def should_enter_warmup(item: WatchItem, warmup_minutes: int, now: datetime) -> bool:
    if item.start_at is None:
        return True
    return now >= item.start_at - timedelta(minutes=warmup_minutes)


def next_sleep(item: WatchItem, interval_seconds: int, warmup_minutes: int, now: datetime) -> float:
    if item.start_at is None:
        return float(interval_seconds)

    warmup_at = item.start_at - timedelta(minutes=warmup_minutes)
    if now < warmup_at:
        return max((warmup_at - now).total_seconds(), 1.0)
    return float(interval_seconds)


def alert(item: WatchItem, reasons: Iterable[str]) -> None:
    reasons_text = ", ".join(reasons)
    print(f"[ALERT] {item.name}: flash sale terdeteksi aktif ({reasons_text})")
    print(f"[ALERT] URL: {item.url}")
    print("\a", end="")


def run(interval_seconds: int, timeout_seconds: int, warmup_minutes: int, items: list[WatchItem]) -> int:
    pending = {item.url: item for item in items}

    while pending:
        for item in list(pending.values()):
            now = normalized_now()

            if not should_enter_warmup(item, warmup_minutes, now):
                sleep_seconds = next_sleep(item, interval_seconds, warmup_minutes, now)
                wake_at = now + timedelta(seconds=sleep_seconds)
                print(
                    f"[WAIT] {item.name}: monitoring aktif mulai sekitar "
                    f"{wake_at.strftime('%Y-%m-%d %H:%M:%S %z')}"
                )
                time.sleep(min(sleep_seconds, 60))
                continue

            timestamp = now.strftime("%Y-%m-%d %H:%M:%S %z")
            try:
                html = fetch_html(item.url, timeout_seconds)
                result = detect_flash_sale(html, item.active_keywords)
                if result.is_active:
                    print(f"[{timestamp}] {item.name}: ACTIVE")
                    alert(item, result.reasons)
                    pending.pop(item.url, None)
                    continue
                print(f"[{timestamp}] {item.name}: belum aktif ({', '.join(result.reasons)})")
            except urllib.error.HTTPError as exc:
                print(f"[{timestamp}] {item.name}: HTTP {exc.code}")
            except urllib.error.URLError as exc:
                print(f"[{timestamp}] {item.name}: gagal koneksi ({exc.reason})")
            except Exception as exc:  # pragma: no cover
                print(f"[{timestamp}] {item.name}: error tidak terduga ({exc})")

            jitter = random.uniform(0, 1.5)
            time.sleep(interval_seconds + jitter)

    return 0


def main() -> int:
    args = parse_args()
    interval_seconds, timeout_seconds, warmup_minutes, items = load_config(args.config)
    if args.interval is not None:
        interval_seconds = args.interval
    if args.timeout is not None:
        timeout_seconds = args.timeout
    print(f"Memantau {len(items)} item. Tekan Ctrl+C untuk berhenti.")
    return run(interval_seconds, timeout_seconds, warmup_minutes, items)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDihentikan oleh user.")
        raise SystemExit(130)
