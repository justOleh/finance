from fastapi import APIRouter, File, HTTPException, UploadFile
from app.schemas import ExpenseCreate, ExpenseResponse, ReceiptDraftResponse
from app.services import expense_service, receipt_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"])



def _validate_and_prepare_upload(file: UploadFile):
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
    return filename, content_type, image_bytes, save_path


@router.post("/parse", response_model=ReceiptDraftResponse)
def parse_receipt(file: UploadFile = File(...)):
    filename, content_type, image_bytes, save_path = _validate_and_prepare_upload(file)

    parsed: dict = {}
    try:
        parsed = receipt_service.parse_receipt_with_service(filename, image_bytes, content_type)
    except Exception as e:
        logger.exception("Failed to parse receipt: %s", e)

    return ReceiptDraftResponse(
        date=receipt_service.parse_expense_date(parsed.get("date")),
        store=parsed.get("store", "Unknown"),
        items=parsed.get("items", []),
        total=float(parsed.get("total", 0.0)),
        notes=str(parsed.get("raw_text", ""))[:500] if parsed.get("raw_text") else None,
        receipt_image_path=save_path,
    )


@router.post("/upload", response_model=ExpenseResponse, status_code=201)
def upload_receipt(file: UploadFile = File(...)):
    filename, content_type, image_bytes, save_path = _validate_and_prepare_upload(file)

    parsed: dict = {}
    try:
        parsed = receipt_service.parse_receipt_with_service(filename, image_bytes, content_type)
    except Exception:
        pass

    return expense_service.create_expense(
        ExpenseCreate(
            date=receipt_service.parse_expense_date(parsed.get("date")),
            store=parsed.get("store", "Unknown"),
            items=parsed.get("items", []),
            total=float(parsed.get("total", 0.0)),
            notes=str(parsed.get("raw_text", ""))[:500] if parsed.get("raw_text") else None,
            receipt_image_path=save_path,
        )
    )
