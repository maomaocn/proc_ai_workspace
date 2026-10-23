from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings
from app.core.errors import AppError


@dataclass(frozen=True)
class MCPToolInfo:
    name: str
    description: str | None
    input_schema: dict[str, Any]


class MCPClient:
    """Adapts an isolated stdio MCP process to the internal Tool Registry contract."""

    def _parameters(self) -> StdioServerParameters:
        env = {
            "DATABASE_URL": settings.database_url,
            "DATABASE_POOL_SIZE": str(settings.database_pool_size),
            "DATABASE_MAX_OVERFLOW": str(settings.database_max_overflow),
            "DATABASE_CONNECT_TIMEOUT_SECONDS": str(settings.database_connect_timeout_seconds),
            "TOOL_MAX_RESULT_ITEMS": str(settings.tool_max_result_items),
            "APP_VERSION": settings.app_version,
        }
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", settings.mcp_server_module],
            env={**os.environ, **env},
            cwd=os.getcwd(),
        )

    async def discover(self) -> tuple[str, str, list[MCPToolInfo]]:
        try:
            async with (
                stdio_client(self._parameters()) as streams,
                ClientSession(
                    *streams,
                    read_timeout_seconds=timedelta(seconds=settings.tool_timeout_seconds),
                ) as session,
            ):
                initialized = await session.initialize()
                self._validate_identity(initialized.serverInfo)
                response = await session.list_tools()
                tools = [
                    MCPToolInfo(
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.inputSchema,
                    )
                    for tool in response.tools
                ]
                return (
                    initialized.serverInfo.name,
                    initialized.serverInfo.version,
                    tools,
                )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(503, "MCP_UNAVAILABLE", "MCP Server 不可用") from exc

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # A fresh protocol session performs handshake/identity validation before every call. Tool
        # results remain untrusted data and are returned through the registry/harness boundaries.
        try:
            async with (
                stdio_client(self._parameters()) as streams,
                ClientSession(
                    *streams,
                    read_timeout_seconds=timedelta(seconds=settings.tool_timeout_seconds),
                ) as session,
            ):
                initialized = await session.initialize()
                self._validate_identity(initialized.serverInfo)
                result = await session.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=timedelta(seconds=settings.tool_timeout_seconds),
                )
                if result.isError:
                    raise AppError(503, "MCP_TOOL_ERROR", "MCP 工具执行失败")
                if not isinstance(result.structuredContent, dict):
                    raise AppError(503, "MCP_RESPONSE_INVALID", "MCP 工具返回格式无效")
                return result.structuredContent
        except AppError:
            raise
        except TimeoutError as exc:
            raise AppError(503, "TOOL_TIMEOUT", "MCP 工具执行超时") from exc
        except Exception as exc:
            raise AppError(503, "MCP_UNAVAILABLE", "MCP Server 不可用") from exc

    @staticmethod
    def _validate_identity(server_info: Any) -> None:
        if server_info is None or server_info.name != settings.mcp_server_expected_name:
            raise AppError(503, "MCP_IDENTITY_MISMATCH", "MCP Server 身份校验失败")


mcp_client = MCPClient()
