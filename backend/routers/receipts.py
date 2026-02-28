"""
backend.routers.receipts
------------------------
FastAPI router for receipt image upload (``/receipts`` prefix).

Workflow
~~~~~~~~
1. Client uploads a JPEG or PNG image via ``POST /receipts/upload``.
2. The image is saved to ``./data/receipts/<uuid>.<ext>`` on disk.
3. The backend forwards the image to the Receipt Parser microservice
   (URL configured via ``RECEIPT_PARSER_URL`` env var).
4. The parsed store, date, items, and total are used to create an
   ``Expense`` record in the database.
5. If the parser service is unavailable the upload still succeeds: an
   expense record is created with ``store="Unknown"`` and ``total=0.0``
   so the user can edit it manually later.

Environment variables
~~~~~~~~~~~~~~~~~~~~~
RECEIPT_PARSER_URL  URL of the Receipt Parser service.
                    Default: ``http://localhost:8001``
"""

import os
import uuid
from datetime import date as date_type
from pathlib import Path
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from models import Expense
from schemas import ExpenseResponse

router = APIRouter(prefix="/receipts", tags=["receipts"])


RECEIPT_PARSER_URL = os.getenv("RECEIPT_PARSER_URL", "http://localhost:8001")
RECEIPTS_DIR = Path("./data/receipts")


def _to_response(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        date=expense.date,
        store=expense.store,
        items=expense.items,
        total=expense.total,
        receipt_image_path=expense.receipt_image_path,
        notes=expense.notes,
        user_id=expense.user_id,
        created_at=expense.created_at,
    )


@router.post("/upload", response_model=ExpenseResponse, status_code=201)
def upload_receipt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are supported")

    # Save file to disk
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix if file.filename else ".jpg"
    filename = f"{uuid.uuid4()}{suffix}"
    save_path = RECEIPTS_DIR / filename
    image_bytes = file.file.read()
    save_path.write_bytes(image_bytes)

    parsed: dict = {}
    try:
        response = httpx.post(
            f"{RECEIPT_PARSER_URL}/parse_receipt",
            files={"file": (filename, image_bytes, file.content_type)},
            timeout=15.0,
        )
        response.raise_for_status()
        parsed = response.json()
    except Exception:
        # Parser unavailable – create a partial expense
        pass

    # Build expense from parsed data (or defaults)
    try:
        expense_date = date_type.fromisoformat(parsed.get("date", "")) if parsed.get("date") else date_type.today()
    except ValueError:
        expense_date = date_type.today()

    expense = Expense(
        date=expense_date,
        store=parsed.get("store", "Unknown"),
        total=float(parsed.get("total", 0.0)),
        notes=parsed.get("raw_text", "")[:500] if parsed.get("raw_text") else None,
        receipt_image_path=str(save_path),
    )
    expense.items = parsed.get("items", [])
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _to_response(expense)
