# 故障排查

## 服务未达到 healthy

```bash
docker compose ps
docker compose logs --tail=200 db api frontend
```

- 数据库端口冲突：设置 `POSTGRES_PORT=55432`；容器内部仍使用 `db:5432`。
- API 反复重启：检查 `DATABASE_URL`/`COMPOSE_DATABASE_URL` 是否混用，以及迁移日志。
- 前端 502：先确认 API `/readyz` 为 200，再检查 Nginx 日志。

## 数据库和迁移

```bash
docker compose exec -T db pg_isready -U app -d enterprise_ai_agent_hub
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

预期迁移为 `20261022_0007 (head)`。不要通过删除 `alembic_version`、清表或移除数据卷修复
迁移问题；先备份并检查连接的数据库是否正确。

## 登录或权限异常

- 401：重新登录并确认 JWT 未过期。
- 403：核对角色边界。审批要求被指派的 `APPROVER`；履约要求 `PROCUREMENT`；
  `TECH_ADMIN` 不具有业务写权限。
- 本地账号缺失：执行 `docker compose exec -T api python -m app.db.seed`，该命令幂等。

## 履约冲突

- `STATE_CONFLICT`：刷新详情，使用最新 `version`，并按相邻状态推进。
- `IDEMPOTENCY_CONFLICT`：同一个键已用于不同负载；为新的业务动作生成新 UUID。
- 请求超时但结果未知：使用完全相同的负载和原幂等键重试，不要自动生成新键。

## MCP、Harness 或 Workflow

- MCP `UNHEALTHY`：检查 `MCP_SERVER_MODULE=app.mcp.server` 和 API 日志。
- `TOOL_NOT_ALLOWED`：工具未进入白名单、角色不匹配或数据库策略被禁用。
- Workflow 恢复失败：检查 checkpoint 数据库 URL 必须是 `postgresql://`，不能带
  `+asyncpg`。

## 收集验收信息

```bash
docker compose ps
curl -sS http://localhost:8000/healthz
curl -sS http://localhost:8000/readyz
conda run -n proc_ai_workspace python scripts/m6_smoke.py --requests 40
git diff --check
```

日志、截图和数据库导出可能包含业务数据；对外共享前必须脱敏。

