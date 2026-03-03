import uuid
from io import BytesIO
from datetime import date as date_type
from pathlib import Path
import httpx
from PIL import Image
from pillow_heif import register_heif_opener
from app.core.config import settings

register_heif_opener()

HEIC_MIME_TYPES = {"image/heic", "image/heif"}


def normalize_parser_payload(payload: dict) -> dict:
    parsed = payload.get("gpt_json") if isinstance(payload.get("gpt_json"), dict) else payload
    if isinstance(parsed, dict) and "where" in parsed and "items" not in parsed:
        parsed["items"] = parsed.get("where", [])
    return parsed if isinstance(parsed, dict) else {}


def convert_heic_to_jpeg(image_bytes: bytes) -> bytes:
    with Image.open(BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        output = BytesIO()
        rgb_image.save(output, format="JPEG", quality=95)
        return output.getvalue()


def prepare_receipt_image(filename: str | None, content_type: str | None, image_bytes: bytes) -> tuple[str, str, bytes]:
    file_ext = Path(filename).suffix.lower() if filename else ""
    current_type = content_type or "application/octet-stream"

    if current_type in HEIC_MIME_TYPES or file_ext in {".heic", ".heif"}:
        image_bytes = convert_heic_to_jpeg(image_bytes)
        current_type = "image/jpeg"
        file_ext = ".jpg"

    suffix = file_ext if file_ext else ".jpg"
    generated_filename = f"{uuid.uuid4()}{suffix}"
    return generated_filename, current_type, image_bytes


def persist_receipt_file(filename: str, image_bytes: bytes) -> str:
    receipts_dir = Path(settings.receipts_dir)
    receipts_dir.mkdir(parents=True, exist_ok=True)
    save_path = receipts_dir / filename
    save_path.write_bytes(image_bytes)
    return str(save_path)


def parse_receipt_with_service(filename: str, image_bytes: bytes, content_type: str) -> dict:
    response = httpx.post(
        f"{settings.receipt_parser_url}/parse_receipt",
        files={"file": (filename, image_bytes, content_type)},
        timeout=15.0,
    )
    response.raise_for_status()
    return normalize_parser_payload(response.json())


def parse_expense_date(raw_date: str | None):
    try:
        return date_type.fromisoformat(raw_date) if raw_date else date_type.today()
    except ValueError:
        return date_type.today()
