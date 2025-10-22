import time
from datetime import datetime
from fastapi import FastAPI, Request

from .api.v1 import api_router
from .config import get_app_config
from .logging_config import log_api_access

app = FastAPI(title="Audio Server", version="1.0.0")
app.include_router(api_router, prefix="/api/v1")

_app_config = get_app_config()


@app.on_event("startup")
async def startup_event():
    _app_config.logger.info(f"Server started at {datetime.now().isoformat()}")

@app.on_event("shutdown")
async def shutdown_event():
    _app_config.logger.info(f"Server stopped at {datetime.now().isoformat()}")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    user_id = request.query_params.get("user_id")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        log_api_access(request.method, request.url.path, user_id, response.status_code, process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        log_api_access(request.method, request.url.path, user_id, 500, process_time, error=str(e))
        _app_config.logger.error(f"{request.method} {request.url.path} failed: {e} ({process_time:.3f}s)")
        raise
