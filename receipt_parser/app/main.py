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

from fastapi import FastAPI

from routers import extract

app = FastAPI(
    title="Receipt Parser Service",
    description=(
        "Stub microservice that accepts a receipt image and returns structured "
        "expense data.  Replace the parser module with a real OCR implementation "
        "when ready."
    ),
)

app.include_router(extract.router)