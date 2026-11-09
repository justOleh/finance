"""Receipt extraction with Claude (ADR-012 / ADR-013), through the Anthropic API.

The API key is read by the SDK from the `ANTHROPIC_API_KEY` environment variable (set on the
Lambda in the AWS console, never in code or Terraform state). The model id, the effort level
and the output size are configuration:

    CLAUDE_MODEL   default claude-sonnet-5-5
    CLAUDE_EFFORT  default medium (low | medium | high | xhigh | max)

Claude Sonnet 5.5 notes: thinking is on by default and cannot be disabled with
`thinking: {"type": "disabled"}`; `temperature`/`top_p`/`top_k`, prefill and a forced
`tool_choice` are rejected. Depth of reasoning is controlled with `output_config.effort`, and
the JSON shape with `output_config.format` (structured outputs), so the reply is always valid
JSON matching RECEIPT_SCHEMA and needs no fence stripping or regex fallback.
"""

import base64
import json
import os
from datetime import UTC, date, datetime

import anthropic

from parse_receipt.engine import ParsedReceipt

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
# Thinking tokens count against max_tokens, so leave generous room (a receipt reply is small).
MAX_TOKENS = 16000
# Worst case is about 2 attempts x 50 s, below the Lambda timeout (see terraform/parse_lambda).
REQUEST_TIMEOUT_SECONDS = 50.0
MAX_RETRIES = 1

SUPPORTED_MEDIA_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

SYSTEM_PROMPT = """You extract structured data from photos of shopping receipts.

Rules:
- Use only what is visible on the receipt. Never guess or invent items, prices or dates.
- "store": the shop name as printed. Empty string if unreadable.
- "date": the purchase date as yyyy-mm-dd. Empty string if no date is visible.
- "items": one entry per purchased line, in receipt order. "name" is the product as printed
  (without the quantity or the price), "price" is the total price of that line as a number with
  a dot as the decimal separator. A separate discount line is an item with a negative price.
- "total": the final amount paid, as a number.
- "notes": short remarks only if useful: the currency, or anything unreadable or uncertain.
  Empty string if there is nothing to say. Do not transcribe the receipt."""

USER_PROMPT = "Extract the data from this receipt."

RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "store": {"type": "string"},
        "date": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "price": {"type": "number"}},
                "required": ["name", "price"],
                "additionalProperties": False,
            },
        },
        "total": {"type": "number"},
        "notes": {"type": "string"},
    },
    "required": ["store", "date", "items", "total", "notes"],
    "additionalProperties": False,
}


class ReceiptParseError(Exception):
    """The model could not (or would not) produce a usable result."""


def _normalise_media_type(content_type: str) -> str:
    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ReceiptParseError(f"Unsupported image type for the model: {content_type!r}")
    return media_type


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


class ClaudeEngine:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        effort: str | None = None,
    ):
        self.model = model or os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.getenv("CLAUDE_EFFORT", DEFAULT_EFFORT)
        self.model_version = self.model
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        # Created on first use so that importing the module (or building the engine) never
        # needs the API key; the SDK reads ANTHROPIC_API_KEY itself.
        if self._client is None:
            self._client = anthropic.Anthropic(
                timeout=REQUEST_TIMEOUT_SECONDS, max_retries=MAX_RETRIES
            )
        return self._client

    def extract(self, image_bytes: bytes, content_type: str) -> ParsedReceipt:
        media_type = _normalise_media_type(content_type)
        image_data = base64.standard_b64encode(image_bytes).decode("ascii")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": RECEIPT_SCHEMA},
            },
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": USER_PROMPT},
                    ],
                }
            ],
        )

        # Always check the stop reason before reading the content.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise ReceiptParseError(f"The model declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            raise ReceiptParseError("The model reply was cut off (max_tokens)")

        text = next((block.text for block in response.content if block.type == "text"), None)
        if not text:
            raise ReceiptParseError("The model returned no text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReceiptParseError(f"The model reply is not valid JSON: {exc}") from exc

        return self._to_receipt(data)

    @staticmethod
    def _to_receipt(data: dict) -> ParsedReceipt:
        notes = (data.get("notes") or "").strip()

        # The backend requires a valid date. If the receipt shows none, fall back to today and
        # say so, so the review form (editable) makes the substitution visible.
        receipt_date = (data.get("date") or "").strip()
        if not _valid_iso_date(receipt_date):
            receipt_date = datetime.now(UTC).date().isoformat()
            notes = f"{notes} Date not found on the receipt; today's date used.".strip()

        items = [
            {"name": str(item["name"]).strip(), "price": float(item["price"])}
            for item in data.get("items") or []
        ]
        return ParsedReceipt(
            store=(data.get("store") or "").strip(),
            date=receipt_date,
            items=items,
            total=float(data.get("total") or 0),
            notes=notes,
        )
