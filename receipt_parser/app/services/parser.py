from datetime import date
import base64
import json
import re
import os
from io import BytesIO
from openai import OpenAI
from fastapi import Request
from dotenv import load_dotenv
from datetime import datetime
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

HEIC_MIME_TYPES = {"image/heic", "image/heif"}

load_dotenv()


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    return OpenAI(api_key=api_key)

RECEIPT_PROMPT = """Extract structured data from this receipt image.
Don't add any information that is not explicitly present in the image.
Return ONLY valid JSON (no markdown, no code fences).
Return a JSON object with keys:
- items (list of {name, amount, unit, unit_price, item_price})
  where each item has:
    - name (str): item description (e.g., "beef")
    - amount (float): quantity (e.g., 0.5)
    - unit (str): unit of measurement (e.g., "kg", "pcs", "l")
    - unit_price (float): price per unit (e.g., 300)
    - item_price (float): total price for this item (e.g., 150)
- store (str): store name
- date (str): date in ISO-8601 format
- total (float): total receipt amount
- raw_text (str): full OCR text from receipt
"""


def _extract_text_from_response(resp) -> str:
    """Extract text content from OpenAI response."""
    if hasattr(resp, "output_text"):
        return resp.output_text
    if hasattr(resp, "output") and resp.output:
        return "".join(item.get("text", "") for item in resp.output)
    return ""


def _parse_json_from_text(text: str) -> dict | None:
    """Parse JSON, stripping markdown code fences if needed."""
    # strip markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _extract_items_from_raw_text(raw_text: str) -> list:
    """Extract items (name, price) from raw text using regex."""
    items = []
    if not raw_text:
        return items
    
    for line in raw_text.splitlines():
        match = re.match(r"^(.*\S)\s+(\d+\.\d{2})$", line.strip())
        if match:
            items.append({"name": match.group(1), "price": float(match.group(2))})
    return items


def convert_heic_to_jpeg(image_bytes: bytes) -> bytes:
    with Image.open(BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        output = BytesIO()
        rgb_image.save(output, format="JPEG", quality=95)
        return output.getvalue()


def prepare_parser_image(filename: str | None, content_type: str | None, image_bytes: bytes) -> tuple[str, str, bytes]:
    file_ext = os.path.splitext(filename or "")[1].lower()
    current_type = content_type or "application/octet-stream"

    if current_type in HEIC_MIME_TYPES or file_ext in {".heic", ".heif"}:
        image_bytes = convert_heic_to_jpeg(image_bytes)
        current_type = "image/jpeg"
        file_ext = ".jpg"

    if not file_ext:
        file_ext = ".jpg" if current_type == "image/jpeg" else ".png"

    output_filename = f"upload{file_ext}"
    return output_filename, current_type, image_bytes


def parse_receipt_image(image_bytes: bytes, content_type: str = "image/jpeg", request: Request = None) -> dict:
    """Send receipt image to OpenAI and return structured data."""
    # If request and Qwen pipeline available, use Qwen
    if request is not None and hasattr(request.app.state, "qwen_pipe"):
        pipe = request.app.state.qwen_pipe
        # Qwen expects a specific message format, so adapt image_bytes accordingly
        # Save image_bytes to a temp file for Qwen pipeline
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": tmp_path},
                    {"type": "text", "text": RECEIPT_PROMPT}
                ]
            },
        ]
        extraction_output = pipe(text=messages)
        assistant_content = extraction_output[0]['generated_text'][1]['content']
        try:
            parsed = json.loads(assistant_content)
        except Exception:
            parsed = None
        return parsed
    # Default: OpenAI fallback
    client = _get_openai_client()
    # encode image as base64 data URL
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{content_type};base64,{b64}"

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "user", "content": RECEIPT_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": data_url}
                ],
            },
        ],
    )

    # Extract and parse response
    output_text = _extract_text_from_response(resp)
    parsed = _parse_json_from_text(output_text)

    # Normalize: if GPT returned "where" instead of "items", rename it
    if parsed and isinstance(parsed, dict):
        if "where" in parsed and "items" not in parsed:
            parsed["items"] = parsed.pop("where")
        
        # Fallback: extract items from raw text if GPT didn't find them
        if not parsed.get("items"):
            parsed["items"] = _extract_items_from_raw_text(parsed.get("raw_text", ""))

        parsed["date"] = datetime.now().date().isoformat()  

    # return {"gpt_result": output_text, "gpt_json": parsed}
    return parsed

