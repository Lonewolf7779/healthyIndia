from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Schema for service health check response.
    """

    status: str = Field(..., description="Service status", examples=["ok"])
    environment: str = Field(..., description="Deployment environment", examples=["local"])
    version: str = Field(..., description="API version", examples=["0.1.0"])
