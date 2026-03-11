from dataclasses import dataclass
import re


@dataclass
class DetectionResult:
    is_active: bool
    reasons: list[str]


def normalize_text(html: str) -> str:
    lowered = html.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def detect_flash_sale(html: str, active_keywords: list[str] | None = None) -> DetectionResult:
    text = normalize_text(html)
    reasons: list[str] = []
    active_keywords = [keyword.lower() for keyword in (active_keywords or []) if keyword.strip()]

    if active_keywords:
        missing = [keyword for keyword in active_keywords if keyword not in text]
        if not missing:
            return DetectionResult(True, [f"keyword:{keyword}" for keyword in active_keywords])
        reasons.append(f"keyword belum lengkap: {', '.join(missing)}")

    generic_markers = [
        ("flash sale", "marker:flash sale"),
        ("stok terbatas", "marker:stok terbatas"),
        ("beli sekarang", "marker:beli sekarang"),
        ("masukkan keranjang", "marker:masukkan keranjang"),
    ]
    matched = [label for needle, label in generic_markers if needle in text]

    # Tanda yang cenderung berarti event sudah live, bukan hanya teaser.
    live_combinations = [
        ("flash sale", "berlangsung"),
        ("flash sale", "habis dalam"),
        ("flash sale", "tersisa"),
        ("flash sale", "beli sekarang"),
        ("flash sale", "masukkan keranjang"),
    ]
    is_live = any(all(part in text for part in combo) for combo in live_combinations)

    if is_live:
        return DetectionResult(True, matched or ["kombinasi marker live"])

    reasons.extend(matched or ["marker live belum terlihat"])
    return DetectionResult(False, reasons)
