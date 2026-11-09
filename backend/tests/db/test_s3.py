from app.db.s3 import get_s3_client


def test_presigned_url_uses_regional_endpoint(monkeypatch):
    # The global endpoint redirects uploads (no CORS headers on the redirect): never use it.
    get_s3_client.cache_clear()
    client = get_s3_client()

    url = client.generate_presigned_post("my-bucket", "receipts/u/1.jpg")["url"]

    assert url == "https://my-bucket.s3.eu-west-1.amazonaws.com/"
    get_s3_client.cache_clear()
