"""
receipt_parser.main
-------------------
FastAPI application entry-point for the Receipt Parser microservice.

This service exposes a single HTTP endpoint (``POST /parse_receipt``) that
accepts a receipt image uploaded as multipart form-data and returns structured
JSON containing the store name, date, line items, and total.

Currently the parsing is handled by a **stub** implementation
(``receipt_parser.parser``) that returns hardcoded sample data so the rest of
the stack can be developed and tested without any OCR dependencies.  Swap in a
real OCR implementation later by updating ``parser.parse_receipt_image`` — the
API contract will not change.

Endpoints
~~~~~~~~~
- ``GET  /health``        → ``{"status": "ok"}``
- ``POST /parse_receipt`` → parsed receipt JSON
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from parser import parse_receipt_image

app = FastAPI(
    title="Receipt Parser Service",
    description=(
        "Stub microservice that accepts a receipt image and returns structured "
        "expense data.  Replace the parser module with a real OCR implementation "
        "when ready."
    ),
)


@app.get("/health", summary="Health check")
def health_check():
    """Return service liveness status."""
    return {"status": "ok"}


@app.post("/parse_receipt", summary="Parse a receipt image")
def parse_receipt(file: UploadFile = File(...)):
    """Accept a JPEG or PNG receipt image and return structured data.

    Returns a JSON object with keys:
    - ``store`` (str)
    - ``date`` (str, ISO-8601)
    - ``items`` (list of ``{name, price}``)
    - ``total`` (float)
    - ``raw_text`` (str)
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are supported")
    image_bytes = file.file.read()
    result = parse_receipt_image(image_bytes)
    return result
