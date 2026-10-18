from app.schemas.health import HealthResponse


def test_health_response_schema() -> None:
    data = {"status": "ok", "environment": "local", "version": "0.1.0"}
    model = HealthResponse(**data)
    assert model.status == "ok"
    assert model.environment == "local"
    assert model.version == "0.1.0"
    assert model.model_dump() == data
