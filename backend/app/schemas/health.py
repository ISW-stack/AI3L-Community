from pydantic import BaseModel


class DependencyStatus(BaseModel):
    name: str
    status: str
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    dependencies: list[DependencyStatus] = []
