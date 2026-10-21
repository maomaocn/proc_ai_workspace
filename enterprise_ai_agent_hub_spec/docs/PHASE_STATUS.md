# 阶段执行状态

> 每阶段由 Codex 在实际实施和验收后更新；未执行阶段保持 NOT_STARTED。

| 阶段 | 状态 | 验收证据 | 遗留问题 |
|---|---|---|---|
| M0 | DONE | 2026-10-21：Ruff、Pytest 6 项、前端 lint/typecheck/build/audit、Compose 三服务、Alembic、健康探针及四档响应式验收通过 | Starlette TestClient 与 ESLint 9 生命周期存在上游弃用提示，不影响当前验收 |
| M1 | NOT_STARTED | 无 | 依赖 M0 |
| M2 | NOT_STARTED | 无 | 依赖 M1 |
| M3 | NOT_STARTED | 无 | 依赖 M2 |
| M4 | NOT_STARTED | 无 | 依赖 M3 |
| M5 | NOT_STARTED | 无 | 依赖 M4 |
| M6 | NOT_STARTED | 无 | 依赖 M5 |

## M0 验收记录（2026-10-21）

- 后端：`ruff check .` 通过；`pytest -q` 为 6 passed；默认 LLM 与 Embedding provider 均为 Mock。
- 前端：`npm run lint`、`npm run typecheck`、`npm run build` 通过；完整 `npm audit` 为 0 vulnerabilities。
- 容器：PostgreSQL 16、FastAPI、Vue/Nginx 三服务构建并达到 healthy；本机验收使用 `POSTGRES_PORT=55432`，未改动已有 PostgreSQL 容器。
- 数据库：Alembic 当前版本为 `20261021_0001 (head)`，`alembic_version` 记录一致。
- 探针：`/healthz` 返回 200；数据库可用时 `/readyz` 返回 200；数据库停止时返回 503，恢复后返回 200；前端 `/api/readyz` 代理返回 200。
- 响应式：在 1440、1280、1024、390 px 宽度完成浏览器检查，无横向溢出，控制台无错误或警告。
