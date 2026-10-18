"""
Cryptographic security utilities for session tokens and data integrity.
Implements timing-attack-resistant HMAC token generation and mandatory extraction session binding.

NOTE ON SECURITY BOUNDARIES & DATA INTEGRITY:
Extraction tokens provide cryptographic SESSION AUTHENTICATION. They verify that an OCR
processing request was genuinely initiated and processed by this server within the expiration
window (default: 1 hour) and bound to a specific extraction session ID.

The token does NOT and CANNOT claim that submitted nutrient values match the raw OCR transcription
on the original label, because healthyIndia explicitly allows users to inspect, correct, and verify
ocr transcription errors before submission. Value integrity against post-confirmation modification
is independently guaranteed through the deterministic confirmed_values_hash.
"""

import hashlib
import hmac
import time
import uuid

from app.core.config import get_settings


def is_valid_uuid(val: str | None) -> bool:
    """
    Validates that a string is a canonical UUID format.
    Rejects missing, empty, whitespace-only, or malformed identifiers.
    """
    if not val or not isinstance(val, str):
        return False
    val = val.strip()
    try:
        parsed = uuid.UUID(val)
        return str(parsed) == val.lower() or str(parsed) == val
    except (ValueError, AttributeError, TypeError):
        return False


def generate_extraction_token(
    extraction_id: str,
    secret_key: str | None = None,
    timestamp: int | None = None,
) -> str:
    """
    Generates a cryptographically signed extraction session token.
    Token format: v1.<extraction_id>.<timestamp>.<signature>

    Args:
        extraction_id: Unique canonical UUID for the OCR extraction session.
        secret_key: Secret key for HMAC signing (defaults to settings.SECRET_KEY).
        timestamp: Unix epoch timestamp in seconds (defaults to current time).

    Returns:
        Formatted signed token string.

    Raises:
        ValueError: If extraction_id is not a valid UUID.
    """
    if not is_valid_uuid(extraction_id):
        raise ValueError(
            f"Cannot generate extraction token for invalid extraction_id '{extraction_id}'. "
            "Must be a canonical UUID."
        )

    if secret_key is None:
        secret_key = get_settings().SECRET_KEY
    if timestamp is None:
        timestamp = int(time.time())

    normalized_id = extraction_id.strip()
    payload = f"v1:{normalized_id}:{timestamp}".encode()
    signature = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"v1.{normalized_id}.{timestamp}.{signature}"


def verify_extraction_token(
    token: str,
    extraction_id: str,
    secret_key: str | None = None,
    max_age_seconds: int = 3600,
    current_time: int | None = None,
) -> tuple[bool, str]:
    """
    Cryptographically verifies an extraction session token against the server secret key
    and strictly binds it to the mandatory extraction_id.
    Uses constant-time comparison to prevent timing attacks.

    No optional-ID verification path is permitted.

    Args:
        token: Signed token string to verify.
        extraction_id: Mandatory expected extraction session UUID to bind against.
        secret_key: Secret key used to verify HMAC (defaults to settings.SECRET_KEY).
        max_age_seconds: Maximum valid age of the token (defaults to 1 hour = 3600s).
        current_time: Reference unix timestamp for testing time-based expiration.

    Returns:
        Tuple of (is_valid: bool, failure_reason: str).
    """
    # 1. Validate extraction_id argument
    if not extraction_id or not isinstance(extraction_id, str) or not extraction_id.strip():
        return False, "Extraction ID is required and cannot be empty."

    if not is_valid_uuid(extraction_id):
        return (
            False,
            f"Malformed extraction_id '{extraction_id}': must be a valid canonical UUID.",
        )

    # 2. Validate token structure
    if not token or not isinstance(token, str):
        return False, "Extraction token is missing or not a string."

    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return False, "Malformed extraction token format: expected 'v1.<id>.<timestamp>.<sig>'."

    version, token_extraction_id, ts_str, signature = parts

    if not is_valid_uuid(token_extraction_id):
        return (
            False,
            (
                "Malformed extraction token: embedded extraction_id "
                f"'{token_extraction_id}' is not a valid UUID."
            ),
        )

    try:
        token_ts = int(ts_str)
    except ValueError:
        return False, "Malformed extraction token timestamp: must be an integer."

    now = current_time if current_time is not None else int(time.time())

    # 3. Clock skew tolerance: max 60 seconds into future
    if token_ts > now + 60:
        return False, "Extraction token timestamp is in the future."

    # 4. Expiration check
    if now - token_ts > max_age_seconds:
        return (
            False,
            f"Extraction token has expired ({now - token_ts}s elapsed, limit {max_age_seconds}s).",
        )

    # 5. Mandatory Extraction ID binding check (constant-time)
    if not hmac.compare_digest(token_extraction_id.lower(), extraction_id.strip().lower()):
        return (
            False,
            f"Extraction token was issued for extraction_id '{token_extraction_id}', "
            f"which does not match provided '{extraction_id}'.",
        )

    # 6. Cryptographic signature check (constant-time)
    if secret_key is None:
        secret_key = get_settings().SECRET_KEY

    expected_payload = f"v1:{token_extraction_id}:{token_ts}".encode()
    expected_signature = hmac.new(
        secret_key.encode("utf-8"), expected_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return False, "Invalid extraction token signature: HMAC verification failed."

    return True, ""
