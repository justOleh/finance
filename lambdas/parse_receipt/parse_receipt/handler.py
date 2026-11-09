"""Lambda "parse receipt" (ADR-013): SQS -> Claude -> DynamoDB.

Triggered by an SQS event source mapping (batch size 1) on the queue fed by the converted
bucket. A message that is not reported back as failed is deleted by Lambda; a failed one becomes
visible again after the visibility timeout and is redelivered, and after `maxReceiveCount`
attempts SQS moves it to the dead-letter queue. On the last attempt the receipt is marked FAILED
so the user sees an error instead of waiting forever.

Configuration (environment variables):
    DYNAMODB_TABLE_NAME  required
    ENGINE               "claude" (default) or "dummy"
    MAX_RECEIVE_COUNT    default 3, keep equal to the queue's maxReceiveCount
    ANTHROPIC_API_KEY    required for ENGINE=claude; set in the Lambda console
    CLAUDE_MODEL, CLAUDE_EFFORT   see claude_engine.py
"""

import logging
import os
from functools import lru_cache

import boto3

from parse_receipt.engine import DummyEngine, Engine
from parse_receipt.processor import mark_failed, process_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lru_cache
def _s3():
    return boto3.client("s3")


@lru_cache
def _table():
    return boto3.resource("dynamodb").Table(os.environ["DYNAMODB_TABLE_NAME"])


@lru_cache
def _engine() -> Engine:
    name = os.getenv("ENGINE", "claude").lower()
    if name == "dummy":
        return DummyEngine()
    if name == "claude":
        from parse_receipt.claude_engine import ClaudeEngine

        return ClaudeEngine()
    raise ValueError(f"Unknown ENGINE {name!r} (expected 'claude' or 'dummy')")


def lambda_handler(event, _context):
    max_receives = int(os.getenv("MAX_RECEIVE_COUNT", "3"))
    failures = []

    for record in event["Records"]:
        body = record["body"]
        try:
            process_message(body, s3=_s3(), table=_table(), engine=_engine())
        except Exception as exc:
            attempt = int(record["attributes"]["ApproximateReceiveCount"])
            logger.exception("Processing failed (attempt %s/%s)", attempt, max_receives)
            if attempt >= max_receives:
                try:
                    mark_failed(body, f"{type(exc).__name__}: {exc}", table=_table())
                except Exception:
                    logger.exception("Could not mark the receipt as FAILED")
            # Reported as failed: not deleted, redelivered, then moved to the DLQ.
            failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": failures}
