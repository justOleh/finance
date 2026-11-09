import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.schemas import ReceiptDraftResponse, ReceiptStatusResponse, ReceiptUploadResponse
from app.services.expense_service import _from_dynamo

# Receipt records live in the same table as expenses (ADR-009 key layout) but have no gsi1
# attributes, so they never show up in expense listings:
#   pk = USER#<sub>, sk = RECEIPT#<id>
# The image is stored at receipts/<sub>/<id>.<ext>. The parser worker derives owner and id
# from that key, so this layout is a contract with receipt_parser/worker (ADR-010).
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def is_supported_content_type(content_type: str) -> bool:
    return content_type in CONTENT_TYPE_EXTENSIONS


def _record_key(user_id: str, receipt_id: str) -> dict[str, str]:
    return {"pk": f"USER#{user_id}", "sk": f"RECEIPT#{receipt_id}"}


def create_upload(
    table,
    s3,
    *,
    bucket: str,
    user_id: str,
    content_type: str,
    expires_in: int,
    max_bytes: int,
) -> ReceiptUploadResponse:
    """Create the receipt record (UPLOADING) and a presigned POST for the image.

    The POST policy pins the Content-Type and a size range, so S3 itself rejects anything
    else; the backend never touches the image bytes.
    """
    receipt_id = uuid.uuid4().hex
    s3_key = f"receipts/{user_id}/{receipt_id}{CONTENT_TYPE_EXTENSIONS[content_type]}"
    now = datetime.now(UTC).isoformat()

    table.put_item(
        Item={
            **_record_key(user_id, receipt_id),
            "id": receipt_id,
            "user_id": user_id,
            "status": "UPLOADING",
            "s3_key": s3_key,
            "content_type": content_type,
            "created_at": now,
            "updated_at": now,
        }
    )

    post = s3.generate_presigned_post(
        Bucket=bucket,
        Key=s3_key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
        ExpiresIn=expires_in,
    )
    return ReceiptUploadResponse(
        receipt_id=receipt_id, upload_url=post["url"], fields=post["fields"]
    )


def get_receipt(table, user_id: str, receipt_id: str) -> ReceiptStatusResponse | None:
    item: dict[str, Any] | None = table.get_item(Key=_record_key(user_id, receipt_id)).get("Item")
    if not item:
        return None

    draft = None
    result = _from_dynamo(item.get("result")) if item.get("result") else None
    if item["status"] == "PARSED" and result:
        draft = ReceiptDraftResponse(
            date=date.fromisoformat(result["date"]),
            store=result["store"],
            items=result["items"],
            total=result["total"],
            notes=result.get("notes"),
            receipt_image_path=item["s3_key"],
        )
    return ReceiptStatusResponse(
        id=receipt_id, status=item["status"], error=item.get("error"), draft=draft
    )
