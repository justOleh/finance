import json
from io import BytesIO
from urllib.parse import quote_plus

import boto3
import pytest
from moto import mock_aws
from PIL import Image

from convert_image import handler

SOURCE = "test-uploads"
DEST = "test-converted"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("DEST_BUCKET", DEST)
    monkeypatch.setenv("MAX_IMAGE_EDGE", "100")
    handler._s3.cache_clear()  # a fresh client per test, inside the moto context
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        for bucket in (SOURCE, DEST):
            client.create_bucket(
                Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
            )
        yield client
    handler._s3.cache_clear()


def _jpeg(size=(300, 200)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (30, 90, 150)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _event(key: str) -> dict:
    # S3 URL-encodes keys in notifications ("/" becomes %2F, " " becomes "+").
    return {"Records": [{"s3": {"bucket": {"name": SOURCE}, "object": {"key": quote_plus(key)}}}]}


def _dest_keys(s3) -> list[str]:
    return [o["Key"] for o in s3.list_objects_v2(Bucket=DEST).get("Contents", [])]


def test_converts_and_writes_png_with_same_key_layout(s3):
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.jpg", Body=_jpeg())

    handler.lambda_handler(_event("receipts/user-a/abc123.jpg"), None)

    assert _dest_keys(s3) == ["receipts/user-a/abc123.png"]
    obj = s3.get_object(Bucket=DEST, Key="receipts/user-a/abc123.png")
    assert obj["ContentType"] == "image/png"
    image = Image.open(BytesIO(obj["Body"].read()))
    assert image.format == "PNG"
    assert image.size == (100, 67)  # downscaled to MAX_IMAGE_EDGE=100


def test_source_object_is_left_untouched(s3):
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.jpg", Body=_jpeg())

    handler.lambda_handler(_event("receipts/user-a/abc123.jpg"), None)

    assert s3.get_object(Bucket=SOURCE, Key="receipts/user-a/abc123.jpg")["Body"].read()


def test_is_idempotent_on_redelivery(s3):
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.jpg", Body=_jpeg())

    handler.lambda_handler(_event("receipts/user-a/abc123.jpg"), None)
    handler.lambda_handler(_event("receipts/user-a/abc123.jpg"), None)

    assert _dest_keys(s3) == ["receipts/user-a/abc123.png"]


def test_s3_test_event_is_ignored(s3):
    event = {"Service": "Amazon S3", "Event": "s3:TestEvent"}

    handler.lambda_handler(event, None)

    assert _dest_keys(s3) == []


def test_key_with_encoded_characters_is_decoded(s3):
    key = "receipts/user+a@example.com/my receipt.jpg"  # "+" and a space
    s3.put_object(Bucket=SOURCE, Key=key, Body=_jpeg())

    handler.lambda_handler(_event(key), None)

    assert _dest_keys(s3) == ["receipts/user+a@example.com/my receipt.png"]


@pytest.mark.parametrize("key", ["other/file.jpg", "receipts/only-two.jpg", "receipts/a/b/c.jpg"])
def test_unexpected_key_layout_raises(s3, key):
    with pytest.raises(ValueError):
        handler.lambda_handler(_event(key), None)

    assert _dest_keys(s3) == []


def test_corrupt_image_raises_and_writes_nothing(s3):
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/bad.jpg", Body=b"not an image")

    with pytest.raises(Exception, match="cannot identify image file"):
        handler.lambda_handler(_event("receipts/user-a/bad.jpg"), None)

    assert _dest_keys(s3) == []


def test_missing_destination_bucket_config_raises(s3, monkeypatch):
    monkeypatch.delenv("DEST_BUCKET")
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.jpg", Body=_jpeg())

    with pytest.raises(KeyError):
        handler.lambda_handler(_event("receipts/user-a/abc123.jpg"), None)


def test_output_key_replaces_only_the_extension():
    assert handler.output_key("receipts/u/id.v2.HEIC") == "receipts/u/id.v2.png"
    assert json.dumps(handler.output_key("receipts/u/noext")) == '"receipts/u/noext.png"'


def _png(size=(60, 40)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_a_ready_png_is_copied_byte_for_byte(s3):
    original = _png()
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.png", Body=original)

    handler.lambda_handler(_event("receipts/user-a/abc123.png"), None)

    copied = s3.get_object(Bucket=DEST, Key="receipts/user-a/abc123.png")
    assert copied["Body"].read() == original
    assert copied["ContentType"] == "image/png"


def test_a_png_that_is_too_large_in_pixels_is_converted_not_copied(s3):
    original = _png((300, 200))  # MAX_IMAGE_EDGE is 100 in these tests
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.png", Body=original)

    handler.lambda_handler(_event("receipts/user-a/abc123.png"), None)

    body = s3.get_object(Bucket=DEST, Key="receipts/user-a/abc123.png")["Body"].read()
    assert body != original
    assert Image.open(BytesIO(body)).size == (100, 67)


def test_a_truncated_png_is_not_copied_and_fails(s3):
    s3.put_object(Bucket=SOURCE, Key="receipts/user-a/abc123.png", Body=_png()[:30])

    with pytest.raises(Exception, match="cannot identify image file|truncated|broken"):
        handler.lambda_handler(_event("receipts/user-a/abc123.png"), None)

    assert _dest_keys(s3) == []
