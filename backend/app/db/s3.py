from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache
def get_s3_client() -> Any:
    """Return an S3 client (FastAPI dependency), used only to sign upload URLs.

    Credentials come from boto3's default chain (profile locally, task role on ECS).
    The regional endpoint is set explicitly: by default boto3 presigns against the global
    `<bucket>.s3.amazonaws.com`, which answers uploads to a bucket outside us-east-1 with a
    307 redirect. The redirect has no CORS headers, so the browser reports a CORS error even
    though the bucket's CORS rules are correct.
    """
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )
