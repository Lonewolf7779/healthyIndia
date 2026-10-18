"""
Cryptographic security utilities for session tokens and data integrity.
Implements timing-attack-resistant HMAC token generation and mandatory extraction session binding.

SECURITY GUARANTEES & CLEARLY BOUNDED SCOPE:
1. Physical Packaging Authenticity:
   Neither cryptographic tokens nor OCR algorithms can prove that a photographed package is
   authentic, unadulterated, compliant with manufacturing standards, or genuine.
2. OCR Transcription Accuracy:
   OCR is probabilistic and fallible. Extraction tokens prove that local OCR was executed
   on this server during an authenticated session; they do NOT prove OCR transcription was 100%
   faithful or free of optical recognition errors.
3. User Inspection & Correction:
   healthyIndia intentionally provides human-in-the-loop inspection and correction of OCR output.
   Users can correct misread numbers or unread fields prior to confirmation.
4. Confirmation Integrity:
   Ordinary unkeyed SHA-256 hashes of client-submitted values do NOT prevent deliberate client
   modification because anyone can compute SHA-256 on arbitrary numbers. Server-keyed confirmation
   tokens ('c1.<id>.<digest>.<timestamp>.<signature>') cryptographically bind the user-reviewed
   values digest to the authenticated extraction session using server-side HMAC-SHA256, guaranteeing
   that submitted values match byte-for-byte what the server acknowledged during confirmation.
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


def generate_confirmation_token(
    extraction_id: str,
    values_digest: str,
    secret_key: str | None = None,
    timestamp: int | None = None,
) -> str:
    """
    Generates a cryptographically signed confirmation token binding reviewed nutrition values
    to an authenticated extraction session.

    Token format: c1.<extraction_id>.<values_digest>.<timestamp>.<signature>

    Args:
        extraction_id: Unique canonical UUID of the OCR extraction session.
        values_digest: 64-character SHA-256 digest of the canonical reviewed values.
        secret_key: Secret key for HMAC signing (defaults to settings.SECRET_KEY).
        timestamp: Unix epoch timestamp in seconds (defaults to current time).

    Returns:
        Formatted signed confirmation token string.

    Raises:
        ValueError: If extraction_id is not a valid UUID or values_digest is not 64 hex characters.
    """
    if not is_valid_uuid(extraction_id):
        raise ValueError(
            f"Cannot generate confirmation token for invalid extraction_id '{extraction_id}'. "
            "Must be a canonical UUID."
        )

    norm_digest = values_digest.strip().lower() if values_digest else ""
    if len(norm_digest) != 64 or not all(c in "0123456789abcdef" for c in norm_digest):
        raise ValueError(
            f"Invalid values_digest '{values_digest}': "
            "must be a 64-character hexadecimal SHA-256 string."
        )

    if secret_key is None:
        secret_key = get_settings().SECRET_KEY
    if timestamp is None:
        timestamp = int(time.time())

    normalized_id = extraction_id.strip()
    payload = f"c1:{normalized_id}:{norm_digest}:{timestamp}".encode()
    signature = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"c1.{normalized_id}.{norm_digest}.{timestamp}.{signature}"


def verify_confirmation_token(
    token: str,
    extraction_id: str,
    expected_digest: str,
    secret_key: str | None = None,
    max_age_seconds: int = 3600,
    current_time: int | None = None,
) -> tuple[bool, str]:
    """
    Cryptographically verifies a confirmation token against the server secret key,
    binding it strictly to the mandatory extraction_id and expected values digest.
    Uses constant-time comparison to prevent timing attacks.

    Args:
        token: Signed confirmation token string to verify.
        extraction_id: Mandatory expected extraction session UUID to bind against.
        expected_digest: Expected 64-character canonical values SHA-256 digest.
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

    # 2. Validate expected_digest argument
    norm_expected = expected_digest.strip().lower() if expected_digest else ""
    if len(norm_expected) != 64 or not all(c in "0123456789abcdef" for c in norm_expected):
        return False, "Expected digest must be a 64-character hexadecimal SHA-256 string."

    # 3. Validate token structure
    if not token or not isinstance(token, str):
        return False, "Confirmation token is missing or not a string."

    parts = token.strip().split(".")
    if len(parts) == 1 and len(parts[0]) == 64:
        return (
            False,
            "Unkeyed SHA-256 hash or malformed token detected; confirmation token "
            "must be a server-keyed token 'c1.<id>.<digest>.<timestamp>.<sig>'.",
        )

    if len(parts) != 5 or parts[0] != "c1":
        return (
            False,
            "Malformed confirmation token format: expected 'c1.<id>.<digest>.<timestamp>.<sig>'.",
        )

    prefix, token_extraction_id, token_digest, ts_str, signature = parts

    if not is_valid_uuid(token_extraction_id):
        return (
            False,
            (
                "Malformed confirmation token: embedded extraction_id "
                f"'{token_extraction_id}' is not a valid UUID."
            ),
        )

    if len(token_digest) != 64:
        return False, "Malformed confirmation token: embedded digest is not 64 characters."

    try:
        token_ts = int(ts_str)
    except ValueError:
        return False, "Malformed confirmation token timestamp: must be an integer."

    now = current_time if current_time is not None else int(time.time())

    # 4. Clock skew tolerance: max 60 seconds into future
    if token_ts > now + 60:
        return False, "Confirmation token timestamp is in the future."

    # 5. Expiration check
    if now - token_ts > max_age_seconds:
        return (
            False,
            (
                f"Confirmation token has expired ({now - token_ts}s elapsed, "
                f"limit {max_age_seconds}s)."
            ),
        )

    # 6. Mandatory Extraction ID binding check (constant-time)
    if not hmac.compare_digest(token_extraction_id.lower(), extraction_id.strip().lower()):
        return (
            False,
            f"Confirmation token was issued for extraction_id '{token_extraction_id}', "
            f"which does not match provided '{extraction_id}'.",
        )

    # 7. Mandatory Digest binding check (constant-time)
    if not hmac.compare_digest(token_digest.lower(), norm_expected):
        return (
            False,
            "Confirmed values token digest does not match submitted values; "
            "values were modified after server confirmation.",
        )

    # 8. Cryptographic signature check (constant-time)
    if secret_key is None:
        secret_key = get_settings().SECRET_KEY

    expected_payload = f"c1:{token_extraction_id}:{token_digest}:{token_ts}".encode()
    expected_signature = hmac.new(
        secret_key.encode("utf-8"), expected_payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return False, "Invalid confirmation token signature: HMAC verification failed."

    return True, ""
