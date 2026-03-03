from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.expense import Expense
from app.schemas import ExpenseResponse
from app.services import receipt_service

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _to_response(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        date=expense.date,
        store=expense.store,
        items=expense.items,
        total=expense.total,
        receipt_image_path=expense.receipt_image_path,
        notes=expense.notes,
        created_at=expense.created_at,
    )


@router.post("/upload", response_model=ExpenseResponse, status_code=201)
def upload_receipt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    allowed_types = {"image/jpeg", "image/png", "image/jpg", "image/heic", "image/heif"}
    file_ext = ""
    if file.filename:
        import pathlib
        file_ext = pathlib.Path(file.filename).suffix.lower()

    if file.content_type not in allowed_types and file_ext not in {".heic", ".heif", ".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, HEIC and HEIF images are supported")

    original_bytes = file.file.read()
    try:
        filename, content_type, image_bytes = receipt_service.prepare_receipt_image(
            file.filename,
            file.content_type,
            original_bytes,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process image: {exc}") from exc

    save_path = receipt_service.persist_receipt_file(filename, image_bytes)

    parsed: dict = {}
    try:
        parsed = receipt_service.parse_receipt_with_service(filename, image_bytes, content_type)
    except Exception:
        pass

    expense = Expense(
        date=receipt_service.parse_expense_date(parsed.get("date")),
        store=parsed.get("store", "Unknown"),
        total=float(parsed.get("total", 0.0)),
        notes=str(parsed.get("raw_text", ""))[:500] if parsed.get("raw_text") else None,
        receipt_image_path=save_path,
    )
    expense.items = parsed.get("items", [])

    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _to_response(expense)
