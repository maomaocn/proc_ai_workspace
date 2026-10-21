from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Enterprise AI Agent Hub"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_version: str = "0.2.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/enterprise_ai_agent_hub"
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)

    jwt_secret_key: str = "local-demo-change-me-before-deployment"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_minutes: int = Field(default=60, ge=5, le=1440)
    seed_demo_data: bool = True

    model_provider: Literal["mock", "openai_compatible"] = "mock"
    embedding_provider: Literal["mock", "remote"] = "mock"

    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = ""
    model_request_timeout_seconds: int = Field(default=20, ge=1, le=120)
    remote_embedding_base_url: str = ""
    remote_embedding_api_key: str = ""
    remote_embedding_model: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_runtime_security(self) -> None:
        if self.app_env == "production" and self.jwt_secret_key.startswith("local-demo"):
            raise ValueError("JWT_SECRET_KEY must be replaced in production")
        if self.app_env == "production" and self.seed_demo_data:
            raise ValueError("SEED_DEMO_DATA must be disabled in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
