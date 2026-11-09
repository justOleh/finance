import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.core.config import settings
from app.db.dynamodb import get_table
from app.db.s3 import get_s3_client
from app.schemas import (
    ExpenseCreate,
    ExpenseResponse,
    ReceiptDraftResponse,
    ReceiptStatusResponse,
    ReceiptUploadRequest,
    ReceiptUploadResponse,
)
from app.services import expense_service, receipt_service, receipt_upload_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"], dependencies=[Depends(get_current_user)])


@router.post("/upload-url", response_model=ReceiptUploadResponse, status_code=201)
def create_upload_url(
    payload: ReceiptUploadRequest,
    user_id: str = Depends(get_current_user),
    table=Depends(get_table),
    s3=Depends(get_s3_client),
):
    """Step 1 of the async pipeline: get a presigned POST to upload the image straight to S3."""
    if not settings.receipts_bucket:
        # Fail closed, like missing Cognito config: a misconfigured deploy must be loud.
        raise HTTPException(status_code=500, detail="RECEIPTS_BUCKET is not configured")
    if not receipt_upload_service.is_supported_content_type(payload.content_type):
        raise HTTPException(
            status_code=400, detail="Only JPEG, PNG, HEIC and HEIF images are supported"
        )
    return receipt_upload_service.create_upload(
        table,
        s3,
        bucket=settings.receipts_bucket,
        user_id=user_id,
        content_type=payload.content_type,
        expires_in=settings.upload_url_expiry_seconds,
        max_bytes=settings.max_upload_bytes,
    )


@router.get("/{receipt_id}", response_model=ReceiptStatusResponse)
def get_receipt(
    receipt_id: str,
    user_id: str = Depends(get_current_user),
    table=Depends(get_table),
):
    """Poll the parsing status; once PARSED it carries the draft for the review form."""
    receipt = receipt_upload_service.get_receipt(table, user_id, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


def _validate_and_prepare_upload(file: UploadFile):
    allowed_types = {"image/jpeg", "image/png", "image/jpg", "image/heic", "image/heif"}
    file_ext = ""
    if file.filename:
        import pathlib

        file_ext = pathlib.Path(file.filename).suffix.lower()

    if file.content_type not in allowed_types and file_ext not in {
        ".heic",
        ".heif",
        ".jpg",
        ".jpeg",
        ".png",
    }:
        raise HTTPException(
            status_code=400, detail="Only JPEG, PNG, HEIC and HEIF images are supported"
        )

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
def upload_receipt(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    table=Depends(get_table),
):
    filename, content_type, image_bytes, save_path = _validate_and_prepare_upload(file)

    parsed: dict = {}
    try:
        parsed = receipt_service.parse_receipt_with_service(filename, image_bytes, content_type)
    except Exception:
        pass

    expense = ExpenseCreate(
        date=receipt_service.parse_expense_date(parsed.get("date")),
        store=parsed.get("store", "Unknown"),
        items=parsed.get("items", []),
        total=float(parsed.get("total", 0.0)),
        notes=str(parsed.get("raw_text", ""))[:500] if parsed.get("raw_text") else None,
        receipt_image_path=save_path,
    )
    return expense_service.create_expense(table, user_id, expense)
