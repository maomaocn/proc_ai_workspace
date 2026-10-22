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
from app.db.session import check_database, close_database


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

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise AI Agent Hub API through M4 procurement approval workflows",
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
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(request.state.request_id)
    return response


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
