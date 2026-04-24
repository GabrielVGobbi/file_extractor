"""JWT Bearer authentication dependency."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(dict):
    """Typed alias for a decoded JWT payload."""


async def verify_jwt(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPayload:
    """Validate the Bearer token and return its decoded payload.

    If ``AUTH_ENABLED`` is false (dev only), returns an empty payload without
    verification — useful for local smoke testing.
    """
    if not settings.auth_enabled:
        return TokenPayload()

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return TokenPayload(payload)


def issue_dev_token(
    settings: Settings,
    subject: str = "dev",
    extra_claims: dict | None = None,
) -> str:
    """Issue a short-lived token for development / smoke tests."""
    import time

    claims: dict = {"sub": subject, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
