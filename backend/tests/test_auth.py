"""
tests/test_auth.py
Unit tests for authentication and channel extraction (api/auth.py).

Spec references:
  F13 — Online (applicant) and Walk-in (employee) channels
"""
import jwt
import pytest
from fastapi import Request

from api.auth import extract_channel_from_token, get_current_channel
from config.settings import get_settings


def test_extract_channel_from_jwt():
    """Verify channel claim extraction from JWT payload."""
    secret = "a_secure_test_secret_key_32_bytes_long!!"
    token_online = jwt.encode({"channel": "online"}, secret, algorithm="HS256")
    assert extract_channel_from_token(token_online) == "online"

    token_walkin = jwt.encode({"channel": "walkin"}, secret, algorithm="HS256")
    assert extract_channel_from_token(token_walkin) == "walkin"

    token_walk_in_hyphen = jwt.encode({"channel": "walk-in"}, secret, algorithm="HS256")
    assert extract_channel_from_token(token_walk_in_hyphen) == "walkin"


@pytest.mark.asyncio
async def test_get_current_channel_header_and_default():
    """Verify X-Channel header fallback and default channel."""
    # With X-Channel header
    scope = {"type": "http", "headers": []}
    req = Request(scope)
    ch = await get_current_channel(req, x_channel="walkin")
    assert ch == "walkin"

    # Default without header
    ch_default = await get_current_channel(req, x_channel=None)
    assert ch_default == "online"
