"""
Cryptographic security utilities for session tokens and data integrity.
Implements timing-attack-resistant HMAC token generation and verification.
"""

import hashlib
import hmac
import time

from app.core.config import get_settings


def generate_extraction_token(
    extraction_id: str,
    secret_key: str | None = None,
    timestamp: int | None = None,
) -> str:
    """
    Generates a cryptographically signed extraction session token.
    Token format: v1.<extraction_id>.<timestamp>.<signature>

    Args:
        extraction_id: Unique UUID identifier for the OCR extraction session.
        secret_key: Secret key for HMAC signing (defaults to settings.SECRET_KEY).
        timestamp: Unix epoch timestamp in seconds (defaults to current time).

    Returns:
        Formatted signed token string.
    """
    if secret_key is None:
        secret_key = get_settings().SECRET_KEY
    if timestamp is None:
        timestamp = int(time.time())

    payload = f"v1:{extraction_id}:{timestamp}".encode()
    signature = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"v1.{extraction_id}.{timestamp}.{signature}"


def verify_extraction_token(
    token: str,
    extraction_id: str | None = None,
    secret_key: str | None = None,
    max_age_seconds: int = 3600,
    current_time: int | None = None,
) -> tuple[bool, str]:
    """
    Cryptographically verifies an extraction session token against the server secret key
    and optional extraction_id binding. Uses constant-time comparison to prevent timing attacks.

    Args:
        token: Signed token string to verify.
        extraction_id: Expected extraction session ID to bind against (optional).
        secret_key: Secret key used to verify the HMAC signature (defaults to settings.SECRET_KEY).
        max_age_seconds: Maximum valid age of the token in seconds (defaults to 1 hour = 3600s).
        current_time: Reference unix timestamp for testing time-based expiration.

    Returns:
        Tuple of (is_valid: bool, failure_reason: str).
    """
    if not token or not isinstance(token, str):
        return False, "Extraction token is missing or not a string."

    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return False, "Malformed extraction token format: expected 'v1.<id>.<timestamp>.<sig>'."

    version, token_extraction_id, ts_str, signature = parts

    try:
        token_ts = int(ts_str)
    except ValueError:
        return False, "Malformed extraction token timestamp: must be an integer."

    now = current_time if current_time is not None else int(time.time())

    # Clock skew tolerance: max 60 seconds into future
    if token_ts > now + 60:
        return False, "Extraction token timestamp is in the future."

    # Expiration check
    if now - token_ts > max_age_seconds:
        return (
            False,
            f"Extraction token has expired ({now - token_ts}s elapsed, limit {max_age_seconds}s).",
        )

    # Extraction ID binding check
    if extraction_id is not None:
        if not hmac.compare_digest(token_extraction_id, extraction_id):
            return (
                False,
                f"Extraction token was issued for extraction_id '{token_extraction_id}', "
                f"which does not match provided '{extraction_id}'.",
            )

    if secret_key is None:
        secret_key = get_settings().SECRET_KEY

    expected_payload = f"v1:{token_extraction_id}:{token_ts}".encode()
    expected_signature = hmac.new(
        secret_key.encode("utf-8"), expected_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return False, "Invalid extraction token signature: HMAC verification failed."

    return True, ""
