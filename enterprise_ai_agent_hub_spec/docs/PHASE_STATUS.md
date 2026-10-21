# 阶段执行状态

> 每阶段由 Codex 在实际实施和验收后更新；未执行阶段保持 NOT_STARTED。

| 阶段 | 状态 | 验收证据 | 遗留问题 |
|---|---|---|---|
| M0 | DONE | 2026-10-21：Ruff、Pytest 6 项、前端 lint/typecheck/build/audit、Compose 三服务、Alembic、健康探针及四档响应式验收通过 | Starlette TestClient 与 ESLint 9 生命周期存在上游弃用提示，不影响当前验收 |
| M1 | DONE | 2026-10-21：Ruff、Pytest 15 项、前端 lint/typecheck/test/build/audit、真实 API 权限与会话隔离、Mock 意图解析和浏览器确认流程通过 | 内置浏览器本轮未提供移动视口缩放；移动端依赖响应式 CSS 与构建检查，后续补充真实设备回归 |
| M2 | DONE | 2026-10-21：Ruff、Pytest 25 项、前端 lint/typecheck/test/build/audit、Alembic 无漂移、真实 API 与浏览器 RAG/ACL/删除验收通过 | 扫描版 PDF 暂不含 OCR；内置浏览器不支持移动视口覆盖，移动端依赖响应式 CSS 与构建检查 |
| M3 | DONE | 2026-10-22：Ruff、Pytest 29 项、前端 lint/typecheck/test/build/audit、Alembic 无漂移、真实 API 与浏览器采购/工具链验收通过 | Starlette TestClient 存在上游 AnyIO 弃用提示；内置浏览器不支持移动视口覆盖，移动端依赖响应式 CSS 与构建检查 |
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
- 演示数据：本地 seed 提供 `employee`、`approver`、`procurement`、`admin`、`techadmin` 五个角色账号；完整凭据、部门和用途记录在项目 `README.md`，生产环境禁止启用。
- 会话隔离：会话及消息持久化至 PostgreSQL；其他用户访问会话返回 403，列表不泄露其他用户会话。
- 意图解析：默认 Mock 模式可复现；“采购10台笔记本，每台6000元”解析为数量 10、单价 6000.00、总预算 60000.00，并追问缺失的采购用途。
- 人工确认：缺失必填字段时返回 422；补充用途后意图状态变为 `CONFIRMED`，响应明确 `purchase_request_created=false`，数据库未创建采购申请表或记录。
- 后端：容器内 `ruff check .` 通过；连接 Compose PostgreSQL 的 `pytest -q` 为 15 passed；Alembic 为 `20261021_0002 (head)` 且 schema 无漂移。
- 前端：`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build` 通过；2 个 Vitest 组件测试通过，完整 `npm audit` 为 0 vulnerabilities。
- 运行验收：PostgreSQL、FastAPI、Vue/Nginx 三服务均为 healthy；`/healthz` 与 `/readyz` 返回 200 和版本 0.2.0；浏览器完成登录、对话、草稿编辑及确认流程。

## M2 验收记录（2026-10-21）

- 知识库与 ACL：新增知识库、授权、文档、片段四张表；默认“企业采购制度”向 `EMPLOYEE` 角色授予只读权限，`TECH_ADMIN` 不自动获得业务知识访问权，`ADMIN` 可管理文档。
- 文档索引：支持 UTF-8 TXT/MD 与含文本层的 PDF，校验扩展名、MIME、文件大小、空内容和重复 SHA-256；按页分块并保留页码，索引状态和失败码持久化至 PostgreSQL。
- RAG：默认使用可复现的本地 Mock Embedding，向量持久化到 Chroma；查询结果再次经过数据库 READY 状态和 ACL 校验，并返回文件名、页码、相似度和原文片段。
- 删除与重建：管理员可重建索引；删除文档会软删除元数据并移除片段、向量与上传文件，实测删除后检索结果为 0。
- 拒答与隔离：无相关依据时固定返回“当前知识库未检索到足够依据。”；普通员工不能上传，技术管理员不能检索未授权知识库，私有知识库不会出现在员工列表或搜索结果中。
- 后端：主机 Conda 环境和容器内 `ruff check .` 均通过；连接 Compose PostgreSQL 的 `pytest -q` 为 25 passed；Alembic 为 `20261021_0003 (head)` 且 `alembic check` 无 schema 漂移。
- 前端：`npm run lint`、`npm run typecheck`、`npm run test -- --run`、`npm run build` 通过；2 个 Vitest 文件、4 项测试通过，完整 `npm audit` 为 0 vulnerabilities。
- 运行验收：三服务均为 healthy；真实 API 完成示例制度上传、命中引用、ACL 403、非法类型 415、删除后不可检索；浏览器完成员工检索、引用详情、无依据拒答和管理员控件检查。

## M3 验收记录（2026-10-22）

- 采购数据：新增库存、供应商、DEMO 报价、采购申请和候选方案五张表；Alembic 为 `20261021_0004 (head)`，`alembic check` 无 schema 漂移，迁移只做增量建表。
- 金额规则：采购草稿、报价和候选金额使用 PostgreSQL `NUMERIC(14,2)` 与 Python `Decimal`；真实 API 验证 10×6000=`60000.00`，最低候选报价 5680×10=`56800.00`。
- 草稿闭环：支持采购列表、新建、详情、版本化编辑和本人资源隔离；确认结构化采购意图会在同一事务创建且只创建一个采购草稿，重复确认幂等返回原草稿。
- Tool Calling：只读注册表实现 `inventory.search`、`supplier.quote`、`policy.search`，具备 Pydantic schema、角色白名单、超时和稳定错误；`TECH_ADMIN` 的业务工具与供应商访问实测返回 403。
- 前端页面：采购列表、新建、详情编辑、候选方案、工具轨迹、制度引用、库存目录和供应商报价页面可用；浏览器实测展示 3 条报价候选及库存/预算风险。
- 后端：主机 Conda 环境和容器内 `ruff check .` 均通过；主机与容器连接 Compose PostgreSQL 的 `pytest` 均为 29 passed；仅有 Starlette TestClient 的上游 AnyIO 弃用提示。
- 前端：`npm run lint`、`npm run typecheck`、`npm test -- --run`、`npm run build` 通过；3 个 Vitest 文件、5 项测试通过，完整 `npm audit` 为 0 vulnerabilities。
- 运行验收：PostgreSQL、FastAPI、Vue/Nginx 三服务均为 healthy；`/healthz`、`/readyz` 和前端返回 200，服务版本为 0.4.0；真实 HTTP 与浏览器采购链路通过。
- 范围控制：未实现提交/取消、审批、LangGraph、履约、MCP 或 Mini Agent Harness，M4-M6 仍保持 NOT_STARTED。
