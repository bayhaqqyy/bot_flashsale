import argparse
import html
import json
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from watcher.detector import DetectionInput, detect_flash_sale
from watcher.renderer import BrowserRenderer

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
    page_type: str = "flash_sale"
    product_terms: list[str] = field(default_factory=list)
    active_keywords: list[str] = field(default_factory=list)
    start_at: datetime | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pantau halaman Shopee sampai produk target muncul di flash sale aktif."
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
        help="Override timeout render dalam detik.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Jalankan browser terlihat, bukan headless.",
    )
    parser.add_argument(
        "--debug-text",
        action="store_true",
        help="Cetak ringkasan teks halaman untuk bantu set keyword.",
    )
    parser.add_argument(
        "--from-file",
        help="Path file teks lokal yang akan dianalisis sekali jalan.",
    )
    parser.add_argument(
        "--html",
        dest="html_file",
        help="Path file HTML lokal yang akan diekstrak lalu dianalisis sekali jalan.",
    )
    parser.add_argument(
        "--product",
        action="append",
        default=[],
        help="Istilah produk target untuk mode --from-file/--html. Bisa diulang.",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="Keyword status aktif untuk mode --from-file/--html. Bisa diulang.",
    )
    parser.add_argument(
        "--page-type",
        default="flash_sale",
        choices=["flash_sale", "product"],
        help="Tipe halaman untuk mode --from-file/--html.",
    )
    return parser.parse_args()


def load_config(path: str) -> tuple[int, int, int, list[WatchItem]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    interval = int(payload.get("interval_seconds", 15))
    timeout = int(payload.get("timeout_seconds", 15))
    warmup = int(payload.get("warmup_minutes", 15))
    items = [parse_item(item) for item in payload.get("items", [])]
    if not items:
        raise ValueError("Config tidak memiliki item untuk dipantau.")
    return interval, timeout, warmup, items


def parse_item(payload: dict) -> WatchItem:
    name = payload["name"]
    url = payload["url"]
    page_type = payload.get("page_type", "flash_sale").strip().lower()
    if page_type not in {"flash_sale", "product"}:
        raise ValueError(f"page_type untuk '{name}' tidak dikenali: {page_type}")

    start_at_raw = payload.get("start_at")
    start_at = None
    if start_at_raw:
        start_at = datetime.fromisoformat(start_at_raw)
        if start_at.tzinfo is None:
            raise ValueError(f"start_at untuk '{name}' harus menyertakan timezone.")

    active_keywords = [keyword.strip().lower() for keyword in payload.get("active_keywords", [])]
    product_terms = [term.strip().lower() for term in payload.get("product_terms", [])]

    return WatchItem(
        name=name,
        url=url,
        page_type=page_type,
        product_terms=product_terms,
        active_keywords=active_keywords,
        start_at=start_at,
    )


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
    print(f"[ALERT] {item.name}: target terdeteksi aktif ({reasons_text})")
    print(f"[ALERT] URL monitor: {item.url}")
    print("\a", end="")


def summarize_text(text: str, limit: int = 500) -> str:
    return " ".join(text.split())[:limit]


def html_to_text(raw_html: str) -> str:
    without_script = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.I | re.S)
    without_style = re.sub(r"<style.*?</style>", " ", without_script, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_style)
    return html.unescape(re.sub(r"\s+", " ", without_tags)).strip()


def fetch_source_html(url: str, timeout_seconds: int) -> str:
    request = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw_body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
        return raw_body.decode(encoding, errors="ignore")


def format_result(label: str, reasons: Iterable[str], prices: list[str]) -> str:
    parts = [", ".join(reasons)]
    if prices:
        parts.append(f"harga: {', '.join(prices[:3])}")
    return f"{label} ({'; '.join(parts)})"


def analyze_local_file(
    file_path: str,
    *,
    treat_as_html: bool,
    page_type: str,
    product_terms: list[str],
    active_keywords: list[str],
    debug_text: bool,
) -> int:
    raw_text = Path(file_path).read_text(encoding="utf-8")
    page_text = html_to_text(raw_text) if treat_as_html else raw_text

    if debug_text:
        print(f"[DEBUG] preview: {summarize_text(page_text)}")

    result = detect_flash_sale(
        DetectionInput(
            page_text=page_text,
            page_type=page_type,
            active_keywords=[keyword.lower() for keyword in active_keywords],
            product_terms=[term.lower() for term in product_terms],
            item_name=file_path,
        )
    )

    if result.is_active:
        print(format_result("ACTIVE", result.reasons, result.prices))
        return 0

    if result.state == "auth_wall":
        print(format_result("AUTH_WALL", result.reasons, result.prices))
        return 2

    print(format_result("INACTIVE", result.reasons, result.prices))
    return 1


def run(
    interval_seconds: int,
    timeout_seconds: int,
    warmup_minutes: int,
    items: list[WatchItem],
    headed: bool,
    debug_text: bool,
) -> int:
    pending = {item.name: item for item in items}
    renderer = BrowserRenderer(timeout_seconds=timeout_seconds, headless=not headed)

    with renderer:
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
                    raw_texts: list[str] = []
                    if item.page_type == "product":
                        try:
                            source_html = fetch_source_html(item.url, timeout_seconds)
                            raw_texts.append(html_to_text(source_html))
                        except (urllib.error.URLError, TimeoutError):
                            pass

                    raw_texts.append(renderer.fetch_text(item.url))
                    page_text = "\n".join(part for part in raw_texts if part.strip())
                    if debug_text:
                        preview = " ".join(page_text.split())[:500]
                        print(f"[DEBUG] {item.name}: {preview}")
                    result = detect_flash_sale(
                        DetectionInput(
                            page_text=page_text,
                            page_type=item.page_type,
                            active_keywords=item.active_keywords,
                            product_terms=item.product_terms,
                            item_name=item.name,
                        )
                    )
                    if result.is_active:
                        suffix = f" | harga: {', '.join(result.prices[:3])}" if result.prices else ""
                        print(f"[{timestamp}] {item.name}: ACTIVE{suffix}")
                        alert(item, result.reasons)
                        pending.pop(item.name, None)
                        continue
                    if item.page_type == "product" and result.prices:
                        print(
                            f"[{timestamp}] {item.name}: harga terdeteksi "
                            f"({', '.join(result.prices[:3])}) | status: {result.availability}"
                        )
                    if result.state == "auth_wall":
                        suffix = f" | harga: {', '.join(result.prices[:3])}" if result.prices else ""
                        print(
                            f"[{timestamp}] {item.name}: perlu akses halaman publik "
                            f"({', '.join(result.reasons)}){suffix}"
                        )
                        pending.pop(item.name, None)
                        continue
                    suffix = f" | harga: {', '.join(result.prices[:3])}" if result.prices else ""
                    print(
                        f"[{timestamp}] {item.name}: belum aktif "
                        f"({', '.join(result.reasons)}) | status: {result.availability}{suffix}"
                    )
                except Exception as exc:  # pragma: no cover
                    print(f"[{timestamp}] {item.name}: error ({exc})")

                jitter = random.uniform(0, 1.5)
                time.sleep(interval_seconds + jitter)

    return 0


def main() -> int:
    args = parse_args()
    if args.from_file or args.html_file:
        source_path = args.from_file or args.html_file
        return analyze_local_file(
            source_path,
            treat_as_html=bool(args.html_file),
            page_type=args.page_type,
            product_terms=args.product,
            active_keywords=args.keyword,
            debug_text=args.debug_text,
        )

    config_path = Path(args.config)
    interval_seconds, timeout_seconds, warmup_minutes, items = load_config(str(config_path))
    if args.interval is not None:
        interval_seconds = args.interval
    if args.timeout is not None:
        timeout_seconds = args.timeout
    print(f"Memantau {len(items)} item. Tekan Ctrl+C untuk berhenti.")
    return run(
        interval_seconds,
        timeout_seconds,
        warmup_minutes,
        items,
        args.headed,
        args.debug_text,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDihentikan oleh user.")
        raise SystemExit(130)
