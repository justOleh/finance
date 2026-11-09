"""Verify Cognito access tokens and expose the caller's id (the token's `sub`).

Flow: the browser signs in with Cognito and sends `Authorization: Bearer <access token>`.
The token is a JWT signed (RS256) by the user pool; we check it against the pool's public
keys (JWKS) and never call Cognito per request.
"""

import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_USER_ID = "local"

# auto_error=False so we return 401 (not FastAPI's default 403) when the header is missing.
_bearer = HTTPBearer(auto_error=False)


def _issuer() -> str:
    return (
        f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"
    )


@lru_cache
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    # PyJWKClient caches the downloaded keys, so JWKS is fetched once, not per request.
    return jwt.PyJWKClient(jwks_url)


def _signing_key(token: str):
    """Public key matching the token's `kid` header (a seam that tests replace)."""
    return _jwks_client(f"{_issuer()}/.well-known/jwks.json").get_signing_key_from_jwt(token).key


def _unauthorized(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency: return the authenticated user's id or raise 401."""
    if settings.auth_disabled:
        return LOCAL_USER_ID
    if not settings.cognito_user_pool_id or not settings.cognito_client_id:
        # Misconfiguration must fail closed, never let requests through.
        raise RuntimeError("COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID are not set")
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    token = credentials.credentials
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            issuer=_issuer(),
            # Access tokens carry `client_id`, not `aud`; it is checked below.
            options={"require": ["exp", "iss", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        logger.info("Rejected token: %s", exc)
        raise _unauthorized() from exc

    if claims.get("token_use") != "access" or claims.get("client_id") != settings.cognito_client_id:
        raise _unauthorized()
    return claims["sub"]
