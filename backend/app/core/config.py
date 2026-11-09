import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Name comes from `terraform output -raw app_table_name`.
    dynamodb_table_name: str = os.getenv("DYNAMODB_TABLE_NAME", "")
    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")
    receipt_parser_url: str = os.getenv("RECEIPT_PARSER_URL", "http://localhost:8001")
    receipts_dir: str = os.getenv("RECEIPTS_DIR", "./data/receipts")
    # Cognito user pool that issues the access tokens (terraform outputs).
    cognito_user_pool_id: str = os.getenv("COGNITO_USER_POOL_ID", "")
    cognito_client_id: str = os.getenv("COGNITO_CLIENT_ID", "")
    # Local development only: skip token checks and act as the fixed user "local".
    # Never set this in AWS.
    auth_disabled: bool = os.getenv("AUTH_DISABLED", "").lower() in {"1", "true", "yes"}
    # Comma-separated browser origins allowed by CORS (the frontend URL).
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    )


settings = Settings()
