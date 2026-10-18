from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings
from app.main import create_app


def test_unhandled_exception_returns_safe_500() -> None:
    faulty_router = APIRouter()

    @faulty_router.get("/faulty-route")
    async def faulty_route() -> None:
        raise RuntimeError("Sensitive internal database connection failure at /var/secrets/db.key")

    test_app = create_app()
    test_app.include_router(faulty_router)

    with TestClient(test_app, raise_server_exceptions=False) as c:
        response = c.get("/faulty-route")
        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "unexpected error" in data["error"]["message"].lower()
        # Verify no traceback or internal filesystem paths were leaked to the client
        assert "RuntimeError" not in response.text
        assert "secrets" not in response.text
        assert "db.key" not in response.text


def test_oversized_payload_rejected_with_413() -> None:
    settings = Settings(
        ENVIRONMENT=Environment.TEST,
        MAX_REQUEST_BODY_BYTES=100,  # 100 bytes limit
    )
    test_app = create_app(settings=settings)

    with TestClient(test_app) as c:
        oversized_data = "x" * 200
        response = c.post(
            "/api/v1/health",
            content=oversized_data,
            headers={"Content-Length": str(len(oversized_data)), "Content-Type": "text/plain"},
        )
        assert response.status_code == 413
        data = response.json()
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
