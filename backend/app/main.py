import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import workflow_runtime
from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import check_database, close_database

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class ReadinessDependencies(BaseModel):
    database: str


class ReadinessResponse(HealthResponse):
    dependencies: ReadinessDependencies


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await workflow_runtime.start()
    try:
        yield
    finally:
        await workflow_runtime.close()
        await close_database()


settings.validate_runtime_security()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="M6 end-to-end enterprise procurement, MCP, Harness and fulfillment API",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = uuid.uuid4()
    request.state.actor_id = None
    request.state.actor_roles = []
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            "request.failed",
            extra={
                "event_data": {
                    "request_id": str(request.state.request_id),
                    "method": request.method,
                    "route": _route_template(request),
                    "duration_ms": _duration_ms(started_at),
                    "actor_id": request.state.actor_id,
                    "actor_roles": request.state.actor_roles,
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise
    response.headers["X-Request-ID"] = str(request.state.request_id)
    log_method = logger.warning if response.status_code >= 400 else logger.info
    log_method(
        "request.completed",
        extra={
            "event_data": {
                "request_id": str(request.state.request_id),
                "method": request.method,
                "route": _route_template(request),
                "status_code": response.status_code,
                "duration_ms": _duration_ms(started_at),
                "actor_id": request.state.actor_id,
                "actor_roles": request.state.actor_roles,
            }
        },
    )
    return response


def _duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


@app.get("/healthz", response_model=HealthResponse, tags=["System"])
async def healthz() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )


@app.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    tags=["System"],
)
async def readyz(
    response: Response,
    database_ready: Annotated[bool, Depends(check_database)],
) -> ReadinessResponse:
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    readiness = "ready" if database_ready else "not_ready"
    database_status = "up" if database_ready else "down"
    return ReadinessResponse(
        status=readiness,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        dependencies=ReadinessDependencies(database=database_status),
    )
