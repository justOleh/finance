from fastapi import FastAPI, UploadFile, File, HTTPException, APIRouter
from app.services.parser import parse_receipt_image


router = APIRouter()


@router.get("/health", summary="Health check")
def health_check():
    """Return service liveness status."""
    return {"status": "ok"}


@router.post("/parse_receipt", summary="Parse a receipt image")
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
    receipt_extraction = parse_receipt_image(image_bytes)
    return receipt_extraction
