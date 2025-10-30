from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.audio import router as audio_router
from app.api.v1.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(audio_router, prefix="/audio", tags=["audio"])
