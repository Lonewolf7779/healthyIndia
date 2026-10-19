"""
Comprehensive security hardening regression test suite for healthyIndia.

Tests:
1. Non-finite float rejection (NaN, Infinity, -Infinity) in nutrition & OCR schemas.
2. Request payload size limits (Content-Length and streaming/chunked transfer bodies).
3. Image upload security (spoofed formats, decompression bombs, oversized dimensions).
4. Sliding-window rate limiting (429 Too Many Requests, Retry-After header, OPTIONS bypass).
5. Environment configuration integrity (production CORS rules, secret key enforcement).
6. Security response headers (CSP, nosniff, frame denial, Permissions-Policy, X-XSS-Protection).
"""

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.core.config import Environment, Settings
from app.core.rate_limit import InMemoryRateLimiter, RateLimitRule
from app.extraction.validator import ImageValidationError, validate_image_payload
from app.main import create_app
from app.schemas.extraction import OcrConfirmationRequest
from app.schemas.nutrition import NutritionAnalysisRequest

# ==============================================================================
# 1. NON-FINITE NUMERICAL VALUE VALIDATION (NaN, Infinity, -Infinity)
# ==============================================================================


def test_nutrition_analysis_request_rejects_nan_serving_size() -> None:
    with pytest.raises(ValidationError, match="serving_size"):
        NutritionAnalysisRequest(
            serving_size=float("nan"),
            is_confirmed=True,
            data_source="manual",
        )


def test_nutrition_analysis_request_rejects_infinity_serving_size() -> None:
    with pytest.raises(ValidationError, match="serving_size"):
        NutritionAnalysisRequest(
            serving_size=float("inf"),
            is_confirmed=True,
            data_source="manual",
        )


def test_nutrition_analysis_request_rejects_nan_in_nutrient_fields() -> None:
    fields = ["energy_kcal", "carbohydrates_g", "protein_g", "total_fat_g", "total_sugar_g"]
    for field_name in fields:
        kwargs = {
            "serving_size": 30.0,
            "is_confirmed": True,
            "data_source": "manual",
            field_name: float("nan"),
        }
        with pytest.raises(ValidationError, match=field_name):
            NutritionAnalysisRequest(**kwargs)


def test_nutrition_analysis_request_rejects_infinity_in_nutrient_fields() -> None:
    for field_name in ["energy_kcal", "carbohydrates_g", "protein_g", "total_fat_g", "sodium_mg"]:
        kwargs = {
            "serving_size": 30.0,
            "is_confirmed": True,
            "data_source": "manual",
            field_name: float("inf"),
        }
        with pytest.raises(ValidationError, match=field_name):
            NutritionAnalysisRequest(**kwargs)


def test_ocr_confirmation_request_rejects_nan_and_infinity() -> None:
    with pytest.raises(ValidationError, match="serving_size"):
        OcrConfirmationRequest(
            extraction_id="550e8400-e29b-41d4-a716-446655440000",
            extraction_token="dummy_token",
            serving_size=float("nan"),
        )

    with pytest.raises(ValidationError, match="energy_kcal"):
        OcrConfirmationRequest(
            extraction_id="550e8400-e29b-41d4-a716-446655440000",
            extraction_token="dummy_token",
            serving_size=30.0,
            energy_kcal=float("inf"),
        )


# ==============================================================================
# 2. PAYLOAD SIZE AND STREAMING BODY BOUNDS (HTTP 413)
# ==============================================================================


def test_json_payload_exceeding_body_limit_returns_413() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        MAX_REQUEST_BODY_BYTES=500,  # Strict 500 byte limit for test
        RATE_LIMIT_ENABLED=False,
    )
    test_app = create_app(settings=settings)

    with TestClient(test_app) as client:
        # Create an oversized payload > 500 bytes
        oversized_json = {
            "ingredients_text": "A" * 600,
        }
        response = client.post("/api/v1/ingredients/analyze", json=oversized_json)
        assert response.status_code == 413
        data = response.json()
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert "exceeds limit" in data["error"]["message"].lower()


def test_streaming_payload_without_content_length_returns_413() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        MAX_REQUEST_BODY_BYTES=200,
        RATE_LIMIT_ENABLED=False,
    )
    test_app = create_app(settings=settings)

    with TestClient(test_app) as client:
        # Stream chunks that exceed 200 bytes total
        def generate_large_stream():
            for _ in range(5):
                yield b"X" * 60

        response = client.post(
            "/api/v1/ingredients/analyze",
            content=generate_large_stream(),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        data = response.json()
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ==============================================================================
# 3. UPLOAD SECURITY & DEFENSIVE IMAGE VALIDATION
# ==============================================================================


def test_spoofed_file_format_rejected() -> None:
    """Non-image bytes disguised as image must be rejected fail-closed."""
    fake_png_payload = b"MZ\x90\x00\x03\x00\x00\x00FakePEExecutableDataFollowsHere" * 10
    with pytest.raises(ImageValidationError) as exc_info:
        validate_image_payload(fake_png_payload)
    assert exc_info.value.code == "INVALID_IMAGE_FORMAT"


def test_empty_or_truncated_image_rejected() -> None:
    """Zero-byte or truncated payloads below minimum size must fail."""
    with pytest.raises(ImageValidationError) as exc_info:
        validate_image_payload(b"short")
    assert exc_info.value.code == "EMPTY_OR_TRUNCATED_IMAGE"


def test_excessive_image_dimension_rejected() -> None:
    """Images exceeding maximum dimension limit must be rejected."""
    buf = io.BytesIO()
    large_img = Image.new("RGB", (5000, 100), color="white")
    large_img.save(buf, format="JPEG")
    large_bytes = buf.getvalue()

    with pytest.raises(ImageValidationError) as exc_info:
        validate_image_payload(large_bytes, max_dimension=4096)
    assert exc_info.value.code == "IMAGE_DIMENSION_EXCEEDED"


def test_decompression_bomb_rejected() -> None:
    """Images exceeding pixel density limit must be rejected."""
    buf = io.BytesIO()
    huge_pixel_img = Image.new("RGB", (3000, 3000), color="white")  # 9 MP
    huge_pixel_img.save(buf, format="PNG")
    huge_bytes = buf.getvalue()

    # Reject if configured max_pixels is lower than 9 MP (e.g. 1 MP)
    with pytest.raises(ImageValidationError) as exc_info:
        validate_image_payload(huge_bytes, max_pixels=1_000_000)
    assert exc_info.value.code in ("DECOMPRESSION_BOMB_DETECTED", "IMAGE_PIXEL_LIMIT_EXCEEDED")


def test_upload_api_rejects_corrupted_file() -> None:
    """API endpoint returns safe client error 422 for corrupted upload."""
    settings = Settings(ENVIRONMENT=Environment.TEST, RATE_LIMIT_ENABLED=False)
    test_app = create_app(settings=settings)

    with TestClient(test_app) as client:
        files = {
            "file": (
                "corrupt.png",
                (
                    b"This is not a real image at all, just plain ASCII text "
                    b"that is long enough to exceed the minimum 64 bytes check."
                ),
                "image/png",
            )
        }
        response = client.post("/api/v1/extraction/ocr", files=files)
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "INVALID_IMAGE_FORMAT"


# ==============================================================================
# 4. SLIDING-WINDOW RATE LIMITING (HTTP 429)
# ==============================================================================


def test_rate_limiter_allows_requests_under_threshold() -> None:
    limiter = InMemoryRateLimiter(
        default_rpm=10,
        rules={"/api/v1/test": RateLimitRule(requests_per_minute=3)},
    )
    # 3 requests allowed
    for _ in range(3):
        allowed, remaining, _ = limiter.check_rate_limit("1.2.3.4", "/api/v1/test")
        assert allowed is True

    # 4th request rejected
    allowed, remaining, retry_after = limiter.check_rate_limit("1.2.3.4", "/api/v1/test")
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_rate_limiter_middleware_returns_429_with_headers() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_ANALYSIS_RPM=2,  # Limit to 2 requests per min for test
    )
    test_app = create_app(settings=settings)

    with TestClient(test_app) as client:
        payload = {"ingredients_text": "Sugar, Salt"}

        # Request 1: OK
        res1 = client.post("/api/v1/ingredients/analyze", json=payload)
        assert res1.status_code == 200
        assert "X-RateLimit-Remaining" in res1.headers

        # Request 2: OK
        res2 = client.post("/api/v1/ingredients/analyze", json=payload)
        assert res2.status_code == 200

        # Request 3: Exceeded -> HTTP 429
        res3 = client.post("/api/v1/ingredients/analyze", json=payload)
        assert res3.status_code == 429
        assert "Retry-After" in res3.headers
        data = res3.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "too many requests" in data["error"]["message"].lower()


def test_rate_limiter_does_not_block_cors_options_preflight() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_ANALYSIS_RPM=1,
    )
    test_app = create_app(settings=settings)

    with TestClient(test_app) as client:
        # Preflight OPTIONS requests should never be blocked by rate limiter
        for _ in range(5):
            res = client.options(
                "/api/v1/ingredients/analyze",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert res.status_code == 200


# ==============================================================================
# 5. ENVIRONMENT & CONFIGURATION CONSTRAINTS
# ==============================================================================


def test_production_environment_rejects_wildcard_cors() -> None:
    with pytest.raises(ValueError, match="Wildcard.*CORS origin is forbidden"):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="a" * 32,
            ALLOWED_ORIGINS=["*"],
        )


def test_production_environment_rejects_localhost_cors() -> None:
    with pytest.raises(ValueError, match="Localhost origin.*is forbidden in production"):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="a" * 32,
            ALLOWED_ORIGINS=["https://healthyindia.com", "http://localhost:3000"],
        )


def test_production_environment_rejects_weak_secret_key() -> None:
    with pytest.raises(ValueError, match="cryptographically strong SECRET_KEY"):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="short-secret",
            ALLOWED_ORIGINS=["https://healthyindia.com"],
        )


# ==============================================================================
# 6. SECURITY HEADERS INTEGRITY
# ==============================================================================


def test_security_headers_include_modern_controls(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    headers = res.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("Content-Security-Policy") == "default-src 'none'; frame-ancestors 'none';"
    assert headers.get("X-XSS-Protection") == "0"
    assert "camera=()" in headers.get("Permissions-Policy", "")


# ==============================================================================
# 7. PHASE 4E: DEFENSE-IN-DEPTH VERIFICATION & EDGE CASES
# ==============================================================================


def test_negative_content_length_rejected() -> None:
    """Negative Content-Length header must be rejected with HTTP 400."""
    settings = Settings(ENVIRONMENT=Environment.TEST, RATE_LIMIT_ENABLED=False)
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        response = client.post(
            "/api/v1/ingredients/analyze",
            content=b'{"ingredients_text": "salt"}',
            headers={"Content-Length": "-1", "Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_misleading_content_length_stream_exceeding_limit_returns_413() -> None:
    """Streams exceeding limit despite misleading small Content-Length must abort with 413."""
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        MAX_REQUEST_BODY_BYTES=200,
        RATE_LIMIT_ENABLED=False,
    )
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:

        def lied_stream():
            for _ in range(10):
                yield b"Y" * 50

        response = client.post(
            "/api/v1/ingredients/analyze",
            content=lied_stream(),
            headers={"Content-Length": "50", "Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_rate_limiter_ignores_spoofed_x_forwarded_for_from_untrusted_client() -> None:
    """X-Forwarded-For must be ignored when connecting host is not in TRUSTED_PROXIES."""
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_ANALYSIS_RPM=2,
        TRUSTED_PROXIES=[],  # No trusted proxies configured
    )
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        payload = {"ingredients_text": "Sugar, Salt"}

        # Request 1 with spoofed IP A
        res1 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        assert res1.status_code == 200

        # Request 2 with spoofed IP B
        res2 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "2.2.2.2"},
        )
        assert res2.status_code == 200

        # Request 3 with spoofed IP C - Should be REJECTED because direct client IP is untrusted
        res3 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "3.3.3.3"},
        )
        assert res3.status_code == 429
        assert res3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limiter_respects_x_forwarded_for_from_trusted_proxy() -> None:
    """X-Forwarded-For is respected only when connecting host is explicitly in TRUSTED_PROXIES."""
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_ANALYSIS_RPM=1,
        TRUSTED_PROXIES=["testclient", "127.0.0.1"],
    )
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        payload = {"ingredients_text": "Sugar, Salt"}

        # Request 1 from Client A via trusted proxy
        res1 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "203.0.113.195"},
        )
        assert res1.status_code == 200

        # Request 2 from Client B via trusted proxy (separate IP bucket -> allowed!)
        res2 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.42"},
        )
        assert res2.status_code == 200

        # Request 3 from Client A again -> exceeds its 1 RPM limit -> HTTP 429
        res3 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "203.0.113.195"},
        )
        assert res3.status_code == 429


def test_rate_limiter_concurrency_and_memory_bounding() -> None:
    """InMemoryRateLimiter is thread-safe and bounds memory consumption under load."""
    import concurrent.futures

    limiter = InMemoryRateLimiter(default_rpm=5, max_tracked_clients=50)

    def worker(client_id: int) -> None:
        client_ip = f"10.0.{client_id // 256}.{client_id % 256}"
        for _ in range(3):
            limiter.check_rate_limit(client_ip, "/api/v1/test")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(100)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Verify that memory is strictly bounded and does not grow unchecked
    assert len(limiter._history) <= 60


def test_confirmation_token_boundary_checks() -> None:
    """Extraction and confirmation tokens enforce canonical UUIDs, HMAC signatures, and expiry."""
    from app.core.security import (
        generate_confirmation_token,
        generate_extraction_token,
        verify_confirmation_token,
        verify_extraction_token,
    )

    valid_id = "550e8400-e29b-41d4-a716-446655440000"
    valid_digest = "a" * 64

    # 1. Invalid extraction UUID rejected
    with pytest.raises(ValueError, match="canonical UUID"):
        generate_extraction_token("not-a-uuid")

    # 2. Tampered signature rejected
    token = generate_extraction_token(valid_id, secret_key="test-key" * 8)
    parts = token.split(".")
    tampered_sig = parts[3][:-4] + "0000"
    tampered_token = f"{parts[0]}.{parts[1]}.{parts[2]}.{tampered_sig}"
    valid, reason = verify_extraction_token(tampered_token, valid_id, secret_key="test-key" * 8)
    assert valid is False
    assert "HMAC verification failed" in reason

    # 3. Extraction ID mismatch rejected
    valid, reason = verify_extraction_token(
        token, "660e8400-e29b-41d4-a716-446655440000", secret_key="test-key" * 8
    )
    assert valid is False
    assert "does not match" in reason

    # 4. Expired token rejected
    old_time = int(time.time()) - 7200
    expired_token = generate_extraction_token(
        valid_id, secret_key="test-key" * 8, timestamp=old_time
    )
    valid, reason = verify_extraction_token(
        expired_token, valid_id, secret_key="test-key" * 8, max_age_seconds=3600
    )
    assert valid is False
    assert "expired" in reason.lower()

    # 5. Confirmation token values_digest binding
    conf_token = generate_confirmation_token(valid_id, valid_digest, secret_key="test-key" * 8)
    altered_digest = "b" * 64
    valid, reason = verify_confirmation_token(
        conf_token, valid_id, altered_digest, secret_key="test-key" * 8
    )
    assert valid is False
    assert "digest does not match" in reason.lower()


# ==============================================================================
# 8. PHASE 4F: RELEASE-GATE EDGE CASE TESTS
# ==============================================================================


def test_rate_limiter_ignores_spoofed_cf_connecting_ip_from_untrusted_client() -> None:
    """CF-Connecting-IP must be ignored when connecting host is not in TRUSTED_PROXIES."""
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_ANALYSIS_RPM=2,
        TRUSTED_PROXIES=[],
    )
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        payload = {"ingredients_text": "Sugar, Salt"}

        # Request 1
        res1 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"CF-Connecting-IP": "103.21.244.1"},
        )
        assert res1.status_code == 200

        # Request 2
        res2 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"CF-Connecting-IP": "103.21.244.2"},
        )
        assert res2.status_code == 200

        # Request 3 -> Exceeded because CF-Connecting-IP was ignored
        res3 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"CF-Connecting-IP": "103.21.244.3"},
        )
        assert res3.status_code == 429
        assert res3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limiter_extracts_leftmost_ip_from_multiple_hops() -> None:
    """X-Forwarded-For with multiple proxies must parse the leftmost client IP."""
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_ANALYSIS_RPM=1,
        TRUSTED_PROXIES=["testclient", "127.0.0.1"],
    )
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        payload = {"ingredients_text": "Sugar, Salt"}

        res1 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "203.0.113.50, 10.0.0.1, 192.168.1.1"},
        )
        assert res1.status_code == 200

        # Re-request with same leftmost IP (even if proxy list varies) -> 429
        res2 = client.post(
            "/api/v1/ingredients/analyze",
            json=payload,
            headers={"X-Forwarded-For": "203.0.113.50, 10.0.0.2"},
        )
        assert res2.status_code == 429


def test_request_size_rejects_invalid_non_numeric_content_length() -> None:
    """Non-numeric Content-Length header returns HTTP 400."""
    settings = Settings(ENVIRONMENT=Environment.TEST, RATE_LIMIT_ENABLED=False)
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        response = client.post(
            "/api/v1/ingredients/analyze",
            content=b'{"ingredients_text": "salt"}',
            headers={"Content-Length": "not-a-number", "Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_oversized_multipart_upload_returns_413() -> None:
    """Upload endpoint rejects files exceeding MAX_IMAGE_UPLOAD_BYTES."""
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        MAX_IMAGE_UPLOAD_BYTES=1000,
        RATE_LIMIT_ENABLED=False,
    )
    test_app = create_app(settings=settings)
    with TestClient(test_app) as client:
        files = {
            "file": (
                "test.png",
                b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000,
                "image/png",
            )
        }
        response = client.post("/api/v1/extraction/ocr", files=files)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_hsts_header_environment_differentiation() -> None:
    """Strict-Transport-Security must be emitted in production and absent in test."""
    # 1. Absent in test environment
    test_settings = Settings(ENVIRONMENT=Environment.TEST, RATE_LIMIT_ENABLED=False)
    test_app = create_app(settings=test_settings)
    with TestClient(test_app) as client:
        res = client.get("/api/v1/health")
        assert "Strict-Transport-Security" not in res.headers

    # 2. Present in production environment
    prod_settings = Settings(
        ENVIRONMENT=Environment.PRODUCTION,
        DEBUG=False,
        SECRET_KEY="x" * 32,
        ALLOWED_ORIGINS=["https://healthyindia.com"],
        RATE_LIMIT_ENABLED=False,
    )
    prod_app = create_app(settings=prod_settings)
    with TestClient(prod_app) as client:
        res = client.get("/api/v1/health")
        assert "Strict-Transport-Security" in res.headers
        assert "includeSubDomains" in res.headers["Strict-Transport-Security"]


def test_extraction_token_additional_edge_cases() -> None:
    """
    Tests future timestamps, secret key mismatches, and malformed token formats
    for extraction tokens.
    """
    from app.core.security import (
        generate_extraction_token,
        verify_extraction_token,
    )

    valid_id = "550e8400-e29b-41d4-a716-446655440000"
    secret = "a" * 32

    # 1. Future timestamp (> 60s in future)
    future_time = int(time.time()) + 300
    future_token = generate_extraction_token(valid_id, secret_key=secret, timestamp=future_time)
    valid, reason = verify_extraction_token(future_token, valid_id, secret_key=secret)
    assert valid is False
    assert "in the future" in reason.lower()

    # 2. Secret key mismatch
    token = generate_extraction_token(valid_id, secret_key=secret)
    valid, reason = verify_extraction_token(token, valid_id, secret_key="b" * 32)
    assert valid is False
    assert "HMAC verification failed" in reason

    # 3. Malformed token formats
    assert verify_extraction_token("not-a-token", valid_id, secret_key=secret)[0] is False
    assert verify_extraction_token("v1.123.456", valid_id, secret_key=secret)[0] is False
    assert verify_extraction_token("v2.123.456.sig", valid_id, secret_key=secret)[0] is False
    assert (
        verify_extraction_token(f"v1.{valid_id}.abc.sig", valid_id, secret_key=secret)[0] is False
    )


def test_confirmation_token_security_edge_cases() -> None:
    """
    Tests confirmation token cryptographic digest binding, future timestamps,
    signature tampering, and value modification rejection.
    """
    from app.core.security import (
        generate_confirmation_token,
        verify_confirmation_token,
    )

    valid_id = "550e8400-e29b-41d4-a716-446655440000"
    valid_digest = "f" * 64
    secret = "k" * 32
    now = int(time.time())

    # 1. Valid confirmation token succeeds
    valid_token = generate_confirmation_token(
        valid_id, values_digest=valid_digest, secret_key=secret, timestamp=now
    )
    ok, err = verify_confirmation_token(
        valid_token, extraction_id=valid_id, expected_digest=valid_digest, secret_key=secret
    )
    assert ok is True
    assert err == ""

    # 2. Nutrition-value modification (digest mismatch) MUST fail
    altered_digest = "0" * 64
    ok, err = verify_confirmation_token(
        valid_token, extraction_id=valid_id, expected_digest=altered_digest, secret_key=secret
    )
    assert ok is False
    assert "digest does not match submitted values" in err

    # 3. Signature tampering MUST fail
    parts = valid_token.split(".")
    tampered_sig = parts[4][:-4] + "dead"
    tampered_token = f"{parts[0]}.{parts[1]}.{parts[2]}.{parts[3]}.{tampered_sig}"
    ok, err = verify_confirmation_token(
        tampered_token, extraction_id=valid_id, expected_digest=valid_digest, secret_key=secret
    )
    assert ok is False
    assert "HMAC verification failed" in err

    # 4. Extraction ID tampering MUST fail
    different_id = "660e8400-e29b-41d4-a716-446655440000"
    ok, err = verify_confirmation_token(
        valid_token, extraction_id=different_id, expected_digest=valid_digest, secret_key=secret
    )
    assert ok is False
    assert "does not match provided" in err

    # 5. Future timestamp (> 60s in future) MUST fail
    future_time = now + 120
    future_conf = generate_confirmation_token(
        valid_id, values_digest=valid_digest, secret_key=secret, timestamp=future_time
    )
    ok, err = verify_confirmation_token(
        future_conf, extraction_id=valid_id, expected_digest=valid_digest, secret_key=secret
    )
    assert ok is False
    assert "in the future" in err.lower()

    # 6. Expired token (> 3600s) MUST fail
    expired_conf = generate_confirmation_token(
        valid_id, values_digest=valid_digest, secret_key=secret, timestamp=now - 4000
    )
    ok, err = verify_confirmation_token(
        expired_conf,
        extraction_id=valid_id,
        expected_digest=valid_digest,
        secret_key=secret,
        max_age_seconds=3600,
    )
    assert ok is False
    assert "expired" in err.lower()

    # 7. Secret key mismatch MUST fail
    ok, err = verify_confirmation_token(
        valid_token,
        extraction_id=valid_id,
        expected_digest=valid_digest,
        secret_key="z" * 32,
    )
    assert ok is False
    assert "HMAC verification failed" in err

    # 8. Unkeyed raw SHA-256 hash or malformed token string MUST fail
    ok, err = verify_confirmation_token(
        valid_digest, extraction_id=valid_id, expected_digest=valid_digest, secret_key=secret
    )
    assert ok is False
    assert "Unkeyed SHA-256 hash or malformed token detected" in err
