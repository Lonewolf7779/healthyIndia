from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health status, environment, and version.",
    status_code=200,
)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Service health check endpoint.
    Safe, unauthenticated probe for readiness and liveness.
    """
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT.value,
        version=settings.APP_VERSION,
    )
