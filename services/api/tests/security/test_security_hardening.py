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
