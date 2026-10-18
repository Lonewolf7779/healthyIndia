from fastapi.testclient import TestClient


def test_baseline_security_headers_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("Content-Security-Policy") == "default-src 'none'; frame-ancestors 'none';"
    assert "camera=()" in headers.get("Permissions-Policy", "")
