import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def test_valid_local_configuration() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.LOCAL,
        DEBUG=True,
        SECRET_KEY="insecure-dev-secret-key-replace-in-production-min-32-chars",
        ALLOWED_ORIGINS=["http://localhost:3000"],
    )
    assert settings.ENVIRONMENT == Environment.LOCAL
    assert settings.DEBUG is True


def test_production_fails_when_debug_enabled() -> None:
    with pytest.raises(ValidationError, match="DEBUG must be False in production"):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=True,
            SECRET_KEY="a-very-secure-random-production-key-min-32-chars-long",
            ALLOWED_ORIGINS=["https://healthyindia.com"],
        )


def test_production_fails_when_secret_key_is_weak_or_default() -> None:
    with pytest.raises(ValidationError, match="cryptographically strong SECRET_KEY"):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="insecure-default-key-too-short",
            ALLOWED_ORIGINS=["https://healthyindia.com"],
        )


def test_production_fails_when_origin_is_wildcard() -> None:
    with pytest.raises(ValidationError, match=r"Wildcard '\*' CORS origin is forbidden"):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="a-very-secure-random-production-key-min-32-chars-long",
            ALLOWED_ORIGINS=["*"],
        )


def test_production_fails_when_origin_is_localhost() -> None:
    with pytest.raises(
        ValidationError, match="Localhost origin 'http://localhost:3000' is forbidden"
    ):
        Settings(
            ENVIRONMENT=Environment.PRODUCTION,
            DEBUG=False,
            SECRET_KEY="a-very-secure-random-production-key-min-32-chars-long",
            ALLOWED_ORIGINS=["http://localhost:3000"],
        )


def test_valid_production_configuration() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.PRODUCTION,
        DEBUG=False,
        SECRET_KEY="a-very-secure-random-production-key-min-32-chars-long",
        ALLOWED_ORIGINS=["https://healthyindia.com", "https://www.healthyindia.com"],
        ALLOWED_HOSTS=["healthyindia.com", "www.healthyindia.com"],
    )
    assert settings.ENVIRONMENT == Environment.PRODUCTION
    assert settings.DEBUG is False
    assert len(settings.ALLOWED_ORIGINS) == 2


def test_parse_comma_separated_origins() -> None:
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:3000, http://127.0.0.1:3000",
    )
    assert settings.ALLOWED_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]
