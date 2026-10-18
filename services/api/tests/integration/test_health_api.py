from fastapi.testclient import TestClient


def test_health_endpoint_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "test"
    assert data["version"] == "0.1.0"


def test_unknown_route_returns_safe_404(client: TestClient) -> None:
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "HTTP_ERROR"
    assert "not found" in data["error"]["message"].lower()
