from fastapi import FastAPI, UploadFile, File, HTTPException, APIRouter
from pathlib import Path
from app.services.parser import parse_receipt_image, prepare_parser_image


router = APIRouter()


@router.get("/health", summary="Health check")
def health_check():
    """Return service liveness status."""
    return {"status": "ok"}


@router.post("/parse_receipt", summary="Parse a receipt image")
def parse_receipt(file: UploadFile = File(...)):
    """Accept a JPEG, PNG, HEIC or HEIF receipt image and return structured data.

    Returns a JSON object with keys:
    - ``store`` (str)
    - ``date`` (str, ISO-8601)
    - ``items`` (list of ``{name, price}``)
    - ``total`` (float)
    - ``raw_text`` (str)
    """
    allowed_types = {"image/jpeg", "image/png", "image/jpg", "image/heic", "image/heif"}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    allowed_ext = {".jpg", ".jpeg", ".png", ".heic", ".heif"}

    if file.content_type not in allowed_types and file_ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, HEIC and HEIF images are supported")

    image_bytes = file.file.read()
    try:
        _, prepared_type, prepared_bytes = prepare_parser_image(file.filename, file.content_type, image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process image: {exc}") from exc

    receipt_extraction = parse_receipt_image(prepared_bytes, content_type=prepared_type)
    return receipt_extraction
