import pytest


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch):
    """Dummy credentials and region so no test can ever reach a real AWS account."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
