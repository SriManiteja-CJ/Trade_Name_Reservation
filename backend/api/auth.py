"""
api/auth.py
Authentication and channel resolution middleware/dependencies.

Spec references:
  F13 — Online (applicant) and Walk-in (employee) channels
  Ambiguity #4 — Configurable JWT algorithm, key, and channel claim name
  N3 — Channel is audited per request
"""
from typing import Optional

import jwt
from fastapi import Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import get_settings

settings = get_settings()
security = HTTPBearer(auto_error=False)


def extract_channel_from_token(token: str) -> Optional[str]:
    """
    Decode JWT and extract the channel claim (F13).
    Returns 'online' or 'walkin', or None if token cannot be verified or claim missing.
    """
    try:
        # If no public key or secret is configured (dev mode), decode without verification
        if not settings.jwt_public_key and not settings.jwt_jwks_url:
            payload = jwt.decode(token, options={"verify_signature": False})
        else:
            key = settings.jwt_public_key
            algorithms = [settings.jwt_algorithm]
            payload = jwt.decode(
                token,
                key=key,
                algorithms=algorithms,
                audience=settings.jwt_audience or None,
                issuer=settings.jwt_issuer or None,
            )
        
        channel_val = payload.get(settings.jwt_channel_claim)
        if channel_val:
            channel_str = str(channel_val).strip().lower()
            if channel_str in ("online", "walkin", "walk-in"):
                return "walkin" if "walk" in channel_str else "online"
        return None
    except jwt.PyJWTError:
        return None


async def get_current_channel(
    request: Request,
    x_channel: Optional[str] = Header(None, alias="X-Channel"),
) -> str:
    """
    FastAPI dependency to extract and normalize the channel for the request.
    Priority:
      1. Valid Bearer JWT token in Authorization header
      2. X-Channel header (for testing / internal gateways)
      3. Default to 'online'
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        channel = extract_channel_from_token(token)
        if channel:
            return channel
        # If public key is configured and token is invalid, reject with 401
        if settings.jwt_public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
            )

    if x_channel:
        ch = x_channel.strip().lower()
        if ch in ("online", "walkin", "walk-in"):
            return "walkin" if "walk" in ch else "online"

    return "online"
