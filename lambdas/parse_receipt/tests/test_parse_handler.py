import json
from urllib.parse import quote_plus

import boto3
import pytest
from moto import mock_aws

from parse_receipt import handler

BUCKET = "test-converted"
OWNER = "user-a"
RECEIPT_ID = "abc123"
KEY = f"receipts/{OWNER}/{RECEIPT_ID}.png"

# Captured at import: a test may replace handler._engine with a plain function.
CACHED = (handler._s3, handler._table, handler._engine)


def _clear_caches():
    for cached in CACHED:
        cached.cache_clear()


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("DYNAMODB_TABLE_NAME", "test-app")
    monkeypatch.setenv("ENGINE", "dummy")
    monkeypatch.setenv("MAX_RECEIVE_COUNT", "3")
    _clear_caches()
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-1")
        s3.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=b"fake-png", ContentType="image/png")
        table = boto3.resource("dynamodb", region_name="eu-west-1").create_table(
            TableName="test-app",
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
        )
        table.put_item(
            Item={"pk": f"USER#{OWNER}", "sk": f"RECEIPT#{RECEIPT_ID}", "status": "UPLOADING"}
        )
        yield table
    _clear_caches()


def _sqs_event(*, receive_count=1, message_id="m1"):
    s3_event = {
        "Records": [{"s3": {"bucket": {"name": BUCKET}, "object": {"key": quote_plus(KEY)}}}]
    }
    return {
        "Records": [
            {
                "messageId": message_id,
                "body": json.dumps(s3_event),
                "attributes": {"ApproximateReceiveCount": str(receive_count)},
            }
        ]
    }


def _item(table):
    return table.get_item(Key={"pk": f"USER#{OWNER}", "sk": f"RECEIPT#{RECEIPT_ID}"})["Item"]


class BrokenEngine:
    model_version = "broken"

    def extract(self, image_bytes, content_type):
        raise RuntimeError("model crashed")


def test_success_stores_the_result_and_reports_no_failures(aws):
    response = handler.lambda_handler(_sqs_event(), None)

    assert response == {"batchItemFailures": []}
    item = _item(aws)
    assert item["status"] == "PARSED"
    assert item["result"]["store"] == "Dummy Market"
    assert item["model_version"] == "dummy-1"
    assert "Item" not in aws.get_item(Key={"pk": f"USER#{OWNER}", "sk": f"EXPENSE#{RECEIPT_ID}"})


def test_failure_is_reported_for_retry_and_the_receipt_is_left_alone(aws, monkeypatch):
    monkeypatch.setattr(handler, "_engine", lambda: BrokenEngine())

    response = handler.lambda_handler(_sqs_event(receive_count=1, message_id="m42"), None)

    assert response == {"batchItemFailures": [{"itemIdentifier": "m42"}]}
    assert _item(aws)["status"] == "UPLOADING"


def test_last_attempt_marks_the_receipt_failed_and_still_reports_the_message(aws, monkeypatch):
    monkeypatch.setattr(handler, "_engine", lambda: BrokenEngine())

    response = handler.lambda_handler(_sqs_event(receive_count=3, message_id="m42"), None)

    assert response == {"batchItemFailures": [{"itemIdentifier": "m42"}]}  # goes on to the DLQ
    item = _item(aws)
    assert item["status"] == "FAILED"
    assert item["error"] == "RuntimeError: model crashed"


def test_one_bad_message_does_not_block_the_others(aws, monkeypatch):
    good = _sqs_event(message_id="good")["Records"][0]
    bad_s3_event = {
        "Records": [{"s3": {"bucket": {"name": BUCKET}, "object": {"key": "other%2Ffile.png"}}}]
    }
    bad = {**good, "messageId": "bad", "body": json.dumps(bad_s3_event)}

    response = handler.lambda_handler({"Records": [bad, good]}, None)

    assert response == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert _item(aws)["status"] == "PARSED"


def test_unknown_engine_is_a_failure_not_a_crash(aws, monkeypatch):
    monkeypatch.setenv("ENGINE", "gpt")
    handler._engine.cache_clear()

    response = handler.lambda_handler(_sqs_event(receive_count=3), None)

    assert response == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
    assert "Unknown ENGINE" in _item(aws)["error"]


def test_engine_defaults_to_claude_and_dummy_is_selectable(monkeypatch):
    handler._engine.cache_clear()
    monkeypatch.delenv("ENGINE", raising=False)
    assert handler._engine().model_version == "claude-sonnet-5-5"

    handler._engine.cache_clear()
    monkeypatch.setenv("ENGINE", "dummy")
    assert handler._engine().model_version == "dummy-1"
    handler._engine.cache_clear()
