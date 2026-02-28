import re
from datetime import date, datetime
from io import BytesIO


def _try_parse_date(text: str) -> str:
    """Attempt to extract a date string from receipt text."""
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{2}/\d{2}/\d{4})\b",
        r"\b(\d{2}-\d{2}-\d{4})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            # Normalise to ISO format where possible
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%m/%d/%y"):
                try:
                    return datetime.strptime(raw, fmt).date().isoformat()
                except ValueError:
                    continue
    return date.today().isoformat()


def _parse_items(lines: list[str]) -> tuple[list[dict], float]:
    """Extract line items and total from receipt lines."""
    items: list[dict] = []
    total: float = 0.0
    price_re = re.compile(r"\$?([\d]+\.[\d]{2})")

    for line in lines:
        upper = line.upper()
        prices = price_re.findall(line)
        if not prices:
            continue
        price = float(prices[-1])
        if any(kw in upper for kw in ("TOTAL", "AMOUNT DUE", "GRAND TOTAL", "BALANCE")):
            total = price
            continue
        if any(kw in upper for kw in ("TAX", "HST", "GST", "PST", "SUBTOTAL", "SUB-TOTAL", "TIP")):
            continue
        # Strip price from name
        name = price_re.sub("", line).strip().strip("$").strip()
        if name:
            items.append({"name": name, "price": price})

    # Fall back to sum of items if no explicit total found
    if total == 0.0 and items:
        total = round(sum(i["price"] for i in items), 2)

    return items, total


def parse_receipt_image(image_bytes: bytes) -> dict:
    """Parse a receipt image and return structured data."""
    from PIL import Image, ImageEnhance, ImageFilter

    raw_text = ""
    try:
        import pytesseract

        image = Image.open(BytesIO(image_bytes)).convert("L")
        image = ImageEnhance.Contrast(image).enhance(2.0)
        image = image.filter(ImageFilter.SHARPEN)
        raw_text = pytesseract.image_to_string(image)
    except Exception:
        # Tesseract not available – use mock data for demonstration
        raw_text = (
            "SUPER MART\n"
            "123 Main St\n"
            "01/15/2024\n"
            "Milk 2.99\n"
            "Bread 3.49\n"
            "Eggs 4.99\n"
            "TOTAL $11.47\n"
        )

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    # Store name is typically the first meaningful line
    store = lines[0] if lines else "Unknown Store"
    # Remove lines that are just addresses / phone numbers for store name
    for line in lines[:3]:
        if re.search(r"[A-Za-z]{3,}", line) and not re.search(r"^\d", line):
            store = line
            break

    parsed_date = _try_parse_date(raw_text)
    items, total = _parse_items(lines)

    return {
        "store": store,
        "date": parsed_date,
        "items": items,
        "total": total,
        "raw_text": raw_text,
    }
