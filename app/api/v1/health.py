"""
Health check endpoint.
Simple status endpoint for monitoring API availability.
"""
from fastapi import APIRouter
from app.models import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
