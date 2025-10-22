from fastapi import APIRouter
from .health import router as health_router
from .audio import router as audio_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(audio_router, prefix="/audio", tags=["audio"])