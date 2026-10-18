from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings, get_settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        ENVIRONMENT=Environment.TEST,
        DEBUG=True,
        SECRET_KEY="test-environment-secret-key-for-unit-testing-32chars",
        ALLOWED_ORIGINS=["http://localhost:3000", "http://testclient.local"],
        ALLOWED_HOSTS=["testserver", "localhost"],
        MAX_REQUEST_BODY_BYTES=1024,  # 1 KB for testing limits easily
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client
