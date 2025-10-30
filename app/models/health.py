"""
Health check response model.
Simple status indicator for API monitoring.
"""
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
