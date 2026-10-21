from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import settings
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
    yield
    await close_database()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise AI Agent Hub API foundation",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
