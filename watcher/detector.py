from dataclasses import dataclass, field
import re


@dataclass
class DetectionInput:
    page_text: str
    page_type: str
    active_keywords: list[str] = field(default_factory=list)
    product_terms: list[str] = field(default_factory=list)
    item_name: str = ""


@dataclass
class DetectionResult:
    is_active: bool
    reasons: list[str]
    state: str = "inactive"
    prices: list[str] = field(default_factory=list)
    availability: str = "unknown"


def normalize_text(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def extract_prices(text: str) -> list[str]:
    patterns = [
        r"rp\s?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?",
        r"\d{1,3}(?:[.,]\d{3})+\s?rp",
    ]
    found: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            normalized = re.sub(r"\s+", " ", match).strip()
            normalized = re.sub(r"^rp", "Rp", normalized, flags=re.I)
            key = normalized.lower()
            if key not in seen:
                seen.add(key)
                found.append(normalized)
    return found


def detect_flash_sale(data: DetectionInput) -> DetectionResult:
    text = normalize_text(data.page_text)
    reasons: list[str] = []
    prices = extract_prices(text)

    login_markers = [
        "log in",
        "login dengan qr",
        "lupa password",
        "baru di shopee? daftar",
    ]
    if sum(1 for marker in login_markers if marker in text) >= 2:
        return DetectionResult(
            False,
            ["halaman yang terbaca adalah login/interstitial, bukan konten flash sale"],
            state="auth_wall",
            prices=prices,
            availability="unknown",
        )

    active_keywords = [keyword.lower() for keyword in data.active_keywords if keyword.strip()]
    product_terms = [term.lower() for term in data.product_terms if term.strip()]

    if data.page_type == "flash_sale":
        status_keywords = active_keywords or ["flash sale", "sedang berjalan"]
        missing_status = [keyword for keyword in status_keywords if keyword not in text]
        if missing_status:
            reasons.append(f"status belum lengkap: {', '.join(missing_status)}")
        else:
            reasons.append("status aktif terdeteksi")

        if product_terms:
            missing_terms = [term for term in product_terms if term not in text]
            if missing_terms:
                reasons.append(f"produk belum terlihat: {', '.join(missing_terms)}")
            else:
                reasons.append("produk target terlihat")

        is_active = not missing_status and (not product_terms or not missing_terms)
        return DetectionResult(
            is_active,
            reasons,
            state="active" if is_active else "inactive",
            prices=prices,
            availability="available" if is_active else "unknown",
        )

    unavailable_markers = [
        "stok habis",
        "sold out",
        "produk tidak ditemukan",
        "produk telah dihapus",
        "barang tidak tersedia",
        "item tidak tersedia",
        "out of stock",
    ]
    matched_unavailable = [marker for marker in unavailable_markers if marker in text]
    if matched_unavailable:
        return DetectionResult(
            False,
            [f"produk tidak tersedia: {', '.join(matched_unavailable)}"],
            state="inactive",
            prices=prices,
            availability="unavailable",
        )

    buy_markers = [
        "beli sekarang",
        "masukkan keranjang",
        "checkout",
    ]
    matched_buy = [marker for marker in buy_markers if marker in text]

    missing_keywords = [keyword for keyword in active_keywords if keyword not in text]
    if active_keywords and not missing_keywords:
        return DetectionResult(
            True,
            [f"keyword:{keyword}" for keyword in active_keywords],
            state="active",
            prices=prices,
            availability="available",
        )

    if not active_keywords:
        if prices and matched_buy:
            return DetectionResult(
                True,
                [f"harga terdeteksi", f"sinyal beli: {', '.join(matched_buy)}"],
                state="active",
                prices=prices,
                availability="available",
            )
        if prices:
            return DetectionResult(
                False,
                ["harga terdeteksi, tapi sinyal beli tidak jelas"],
                state="inactive",
                prices=prices,
                availability="unknown",
            )
        return DetectionResult(
            False,
            ["harga belum terdeteksi"],
            state="inactive",
            prices=prices,
            availability="unknown",
        )

    generic_markers = [
        ("flash sale", "marker:flash sale"),
        ("stok terbatas", "marker:stok terbatas"),
        ("beli sekarang", "marker:beli sekarang"),
        ("masukkan keranjang", "marker:masukkan keranjang"),
    ]
    matched = [label for needle, label in generic_markers if needle in text]
    reasons.append(f"keyword belum lengkap: {', '.join(missing_keywords)}")
    reasons.extend(matched or ["marker live belum terlihat"])
    return DetectionResult(
        False,
        reasons,
        state="inactive",
        prices=prices,
        availability="available" if prices else "unknown",
    )
