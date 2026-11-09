"""Lambda "convert image" (ADR-013): uploads bucket -> PNG in the converted bucket.

Triggered by S3 `ObjectCreated` on the uploads bucket (asynchronous invocation). The object
key `receipts/<owner>/<receipt_id>.<ext>` is written by the backend (ADR-010); the PNG keeps
the same key with a `.png` extension, so the parse Lambda finds owner and id the same way.
A PNG that is already usable as it is (valid, small enough, not rotated) is copied unchanged;
every other image is converted.

Any exception makes the invocation fail: Lambda retries asynchronously, and after the last
retry the event goes to the on-failure destination (an SQS queue) instead of being lost.
The output key is deterministic, so a retry simply overwrites the same object.
"""

import logging
import os
from functools import lru_cache
from urllib.parse import unquote_plus

import boto3

from convert_image.converter import convert_to_png, is_ready_png

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_MAX_EDGE = 2000


@lru_cache
def _s3():
    return boto3.client("s3")


def output_key(key: str) -> str:
    """`receipts/<owner>/<id>.<ext>` -> `receipts/<owner>/<id>.png`; reject other layouts."""
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "receipts" or not parts[2]:
        raise ValueError(f"Unexpected object key: {key!r}")
    return f"receipts/{parts[1]}/{parts[2].rsplit('.', 1)[0]}.png"


def lambda_handler(event, _context):
    destination = os.environ["DEST_BUCKET"]
    max_edge = int(os.getenv("MAX_IMAGE_EDGE", str(DEFAULT_MAX_EDGE)))

    # S3 sends no Records for a one-off s3:TestEvent: nothing to do.
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        # Keys arrive URL-encoded ("+" for spaces, %XX for the rest).
        key = unquote_plus(record["s3"]["object"]["key"])
        target = output_key(key)

        body = _s3().get_object(Bucket=bucket, Key=key)["Body"].read()
        # A PNG that is already fine for the parser is copied byte for byte: re-encoding would
        # only cost time and can make the file bigger.
        if is_ready_png(body, max_edge):
            png, action = body, "Copied"
        else:
            png, action = convert_to_png(body, max_edge), "Converted"
        _s3().put_object(Bucket=destination, Key=target, Body=png, ContentType="image/png")
        logger.info(
            "%s s3://%s/%s (%d B) -> %s (%d B)", action, bucket, key, len(body), target, len(png)
        )
