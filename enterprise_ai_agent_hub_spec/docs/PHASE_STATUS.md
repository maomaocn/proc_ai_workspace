# 阶段执行状态

> 每阶段由 Codex 在实际实施和验收后更新；未执行阶段保持 NOT_STARTED。

| 阶段 | 状态 | 验收证据 | 遗留问题 |
|---|---|---|---|
| M0 | DONE | 2026-10-21：Ruff、Pytest 6 项、前端 lint/typecheck/build/audit、Compose 三服务、Alembic、健康探针及四档响应式验收通过 | Starlette TestClient 与 ESLint 9 生命周期存在上游弃用提示，不影响当前验收 |
| M1 | DONE | 2026-10-21：Ruff、Pytest 15 项、前端 lint/typecheck/test/build/audit、真实 API 权限与会话隔离、Mock 意图解析和浏览器确认流程通过 | 内置浏览器本轮未提供移动视口缩放；移动端依赖响应式 CSS 与构建检查，后续补充真实设备回归 |
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

## M1 验收记录（2026-10-21）

- 身份与权限：JWT 登录、`/auth/me`、部门及多角色关系可用；未登录返回 401，普通员工和技术管理员访问业务管理员接口返回 403，管理员可读取用户列表。
- 会话隔离：会话及消息持久化至 PostgreSQL；其他用户访问会话返回 403，列表不泄露其他用户会话。
- 意图解析：默认 Mock 模式可复现；“采购10台笔记本，每台6000元”解析为数量 10、单价 6000.00、总预算 60000.00，并追问缺失的采购用途。
- 人工确认：缺失必填字段时返回 422；补充用途后意图状态变为 `CONFIRMED`，响应明确 `purchase_request_created=false`，数据库未创建采购申请表或记录。
- 后端：容器内 `ruff check .` 通过；连接 Compose PostgreSQL 的 `pytest -q` 为 15 passed；Alembic 为 `20261021_0002 (head)` 且 schema 无漂移。
- 前端：`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build` 通过；2 个 Vitest 组件测试通过，完整 `npm audit` 为 0 vulnerabilities。
- 运行验收：PostgreSQL、FastAPI、Vue/Nginx 三服务均为 healthy；`/healthz` 与 `/readyz` 返回 200 和版本 0.2.0；浏览器完成登录、对话、草稿编辑及确认流程。
