"""
receipt_parser.parser
---------------------
Stub receipt-parsing module.

This module provides a placeholder implementation of receipt parsing that
returns a fixed hardcoded response.  It is intentionally simple so the rest
of the system (backend API + Streamlit UI) can be developed and tested
end-to-end without requiring Tesseract OCR or any external dependencies.

When real OCR is needed in the future, replace ``parse_receipt_image`` with
an implementation that calls an OCR library (e.g. pytesseract, Google Vision)
or a third-party API.  The returned dict shape must stay the same so that
``receipt_parser.main`` and ``backend.routers.receipts`` keep working without
modification.

Returned dict schema
~~~~~~~~~~~~~~~~~~~~
{
    "store":    str,          # merchant / store name
    "date":     str,          # ISO-8601 date string (YYYY-MM-DD)
    "items":    list[dict],   # each item: {"name": str, "price": float}
    "total":    float,        # total amount
    "raw_text": str,          # raw source text (empty for the stub)
}
"""

from datetime import date


# ---------------------------------------------------------------------------
# Hardcoded sample receipt used by the stub
# ---------------------------------------------------------------------------
_STUB_RESPONSE: dict = {
    "store": "Sample Supermarket",
    "date": date.today().isoformat(),
    "items": [
        {"name": "Milk (1 L)", "price": 2.99},
        {"name": "Sourdough Bread", "price": 3.49},
        {"name": "Free-Range Eggs (12)", "price": 4.99},
    ],
    "total": 11.47,
    "raw_text": "",
}


def parse_receipt_image(image_bytes: bytes) -> dict:  # noqa: ARG001
    """Return a hardcoded sample receipt regardless of the image content.

    Args:
        image_bytes: Raw bytes of the uploaded receipt image (unused by the
            stub but required so the signature matches the real implementation).

    Returns:
        A dict with keys ``store``, ``date``, ``items``, ``total``, and
        ``raw_text``.
    """
    # Refresh the date stamp each call so records get today's date.
    return {**_STUB_RESPONSE, "date": date.today().isoformat()}
