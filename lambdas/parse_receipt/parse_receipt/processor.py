"""Handle one SQS message: an S3 `ObjectCreated` notification for a converted receipt PNG.

The S3 key is `receipts/<owner>/<receipt_id>.png`: the backend writes the layout (ADR-010) and
the convert Lambda sets the extension (ADR-013). Owner and id are read from it, so the Lambda
needs nothing else to find the receipt record (`pk = USER#<owner>`, `sk = RECEIPT#<receipt_id>`).

On success the result is stored as a draft on the receipt record (status PARSED). The browser
polls the backend, shows the draft in an editable form, and only the user's Save creates the
expense, so a wrong parse never lands in the user's data unreviewed. A photo from which neither
items nor a total can be read is marked FAILED instead of producing an empty draft.

Delivery is at-least-once, so everything here is idempotent: processing the same message twice
writes the same result to the same item.
"""

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import unquote_plus

from parse_receipt.engine import Engine, ParsedReceipt

logger = logging.getLogger(__name__)

UNREADABLE_MESSAGE = (
    "Не вдалося прочитати позиції та суму з фото. Можливо, на ньому видно лише частину чека."
)


@dataclass(frozen=True)
class UploadedReceipt:
    bucket: str
    key: str
    owner: str
    receipt_id: str


def _iter_uploads(body: str) -> Iterator[UploadedReceipt]:
    event = json.loads(body)
    # S3 sends a one-off s3:TestEvent when the notification is configured: nothing to do.
    for record in event.get("Records", []):
        # Keys arrive URL-encoded ("+" for spaces, %XX for the rest).
        key = unquote_plus(record["s3"]["object"]["key"])
        parts = key.split("/")
        if len(parts) != 3 or parts[0] != "receipts":
            raise ValueError(f"Unexpected object key: {key!r}")
        yield UploadedReceipt(
            bucket=record["s3"]["bucket"]["name"],
            key=key,
            owner=parts[1],
            receipt_id=parts[2].rsplit(".", 1)[0],
        )


def _record_key(upload: UploadedReceipt) -> dict[str, str]:
    return {"pk": f"USER#{upload.owner}", "sk": f"RECEIPT#{upload.receipt_id}"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _to_dynamo(value):
    """boto3 rejects float: round-trip through JSON to get Decimal numbers."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _is_unreadable(parsed: ParsedReceipt) -> bool:
    return not parsed.items and not parsed.total


def process_message(body: str, *, s3, table, engine: Engine) -> None:
    """Download each converted image, extract it, and store the draft on the receipt record.

    Raises on any failure, so the caller leaves the message in the queue (retry, then DLQ).
    """
    for upload in _iter_uploads(body):
        obj = s3.get_object(Bucket=upload.bucket, Key=upload.key)
        parsed = engine.extract(obj["Body"].read(), obj["ContentType"])

        if _is_unreadable(parsed):
            # Retrying cannot help (same photo, same answer): fail the receipt now and let the
            # message be deleted instead of paying for three more model calls.
            _mark_upload_failed(upload, UNREADABLE_MESSAGE, table=table)
            logger.warning("Nothing readable on receipt %s for %s", upload.receipt_id, upload.owner)
            continue

        # Condition: only update a record the backend created. An orphan upload raises
        # ConditionalCheckFailed and ends up in the DLQ instead of creating a ghost item.
        table.update_item(
            Key=_record_key(upload),
            UpdateExpression=(
                "SET #status = :status, #result = :result, model_version = :model, "
                "updated_at = :now REMOVE #error"
            ),
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeNames={"#status": "status", "#result": "result", "#error": "error"},
            ExpressionAttributeValues={
                ":status": "PARSED",
                ":result": _to_dynamo(
                    {
                        "store": parsed.store,
                        "date": parsed.date,
                        "items": parsed.items,
                        "total": parsed.total,
                        "notes": parsed.notes[:500] or None,
                    }
                ),
                ":model": engine.model_version,
                ":now": _now(),
            },
        )

        logger.info("Parsed receipt %s for %s", upload.receipt_id, upload.owner)


def _mark_upload_failed(upload: UploadedReceipt, error: str, *, table) -> None:
    table.update_item(
        Key=_record_key(upload),
        UpdateExpression="SET #status = :status, #error = :error, updated_at = :now",
        ConditionExpression="attribute_exists(pk)",
        ExpressionAttributeNames={"#status": "status", "#error": "error"},
        ExpressionAttributeValues={
            ":status": "FAILED",
            ":error": error[:500],
            ":now": _now(),
        },
    )


def mark_failed(body: str, error: str, *, table) -> None:
    """Record the failure so the receipt is not left UPLOADING (called on the last attempt)."""
    for upload in _iter_uploads(body):
        _mark_upload_failed(upload, error, table=table)
