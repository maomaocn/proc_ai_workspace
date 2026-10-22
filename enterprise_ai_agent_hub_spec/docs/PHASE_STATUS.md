# 阶段执行状态

> 每阶段由 Codex 在实际实施和验收后更新；未执行阶段保持 NOT_STARTED。

| 阶段 | 状态 | 验收证据 | 遗留问题 |
|---|---|---|---|
| M0 | DONE | 2026-10-21：Ruff、Pytest 6 项、前端 lint/typecheck/build/audit、Compose 三服务、Alembic、健康探针及四档响应式验收通过 | Starlette TestClient 与 ESLint 9 生命周期存在上游弃用提示，不影响当前验收 |
| M1 | DONE | 2026-10-21：Ruff、Pytest 15 项、前端 lint/typecheck/test/build/audit、真实 API 权限与会话隔离、Mock 意图解析和浏览器确认流程通过 | 内置浏览器本轮未提供移动视口缩放；移动端依赖响应式 CSS 与构建检查，后续补充真实设备回归 |
| M2 | DONE | 2026-10-21：Ruff、Pytest 25 项、前端 lint/typecheck/test/build/audit、Alembic 无漂移、真实 API 与浏览器 RAG/ACL/删除验收通过 | 扫描版 PDF 暂不含 OCR；内置浏览器不支持移动视口覆盖，移动端依赖响应式 CSS 与构建检查 |
| M3 | DONE | 2026-10-22：Ruff、Pytest 29 项、前端 lint/typecheck/test/build/audit、Alembic 无漂移、真实 API 与浏览器采购/工具链验收通过 | Starlette TestClient 存在上游 AnyIO 弃用提示；内置浏览器不支持移动视口覆盖，移动端依赖响应式 CSS 与构建检查 |
| M4 | DONE | 2026-10-22：LangGraph PostgreSQL checkpoint、阈值与顺序审批、自审拒绝、幂等/并发/审计、Ruff、Pytest 35 项、前端 7 项测试及构建、Compose 与真实 HTTP/浏览器验收通过 | Starlette TestClient 存在上游 AnyIO 弃用提示；采购履约、MCP 与 Harness 按计划留待后续阶段 |
| M5 | DONE | 2026-10-22：独立 stdio MCP、统一工具注册表、Mini Agent Harness、持久化轨迹/SSE、Ruff、Pytest 39 项、前端 8 项测试及构建、Alembic/Compose/真实 HTTP/浏览器验收通过 | Starlette TestClient 存在上游 AnyIO 弃用提示；生产级远程 MCP、采购履约与 ERP 集成留待后续阶段 |
| M6 | DONE | 2026-10-22：AC-01 至 AC-20、Mock 全链路履约、持久化 SSE、脱敏 JSON 日志、Ruff、Pytest 46 项、前端 11 项测试/构建/audit、Alembic/Compose、40 次只读 smoke 和四档浏览器验收通过 | 真实 ERP/供应商/支付/物流、生产远程 MCP/OCR/高可用不在本地交付范围；Starlette TestClient 有上游 AnyIO 弃用提示 |

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
- 范围控制：当时未实现提交/取消、审批、LangGraph、履约、MCP 或 Mini Agent Harness，M4-M6 保持 NOT_STARTED。

## M4 验收记录（2026-10-22）

- 审批规则：数据库规则实现 `<=10000.00` 一级、`>10000.00` 两级顺序审批；提交前预览返回部门负责人 `manager` 和财务审批人 `approver`，规则缺失、级别缺口或同级金额重叠均拒绝流转。
- LangGraph：真实 `StateGraph` 使用 `interrupt()` 暂停和 `Command(resume=...)` 恢复；官方 PostgreSQL saver 采用同步 durability，checkpoint 通过独立 psycopg 连接持久化，未使用进程内 MemorySaver。
- 事务安全：提交、草稿取消和审批决策要求 UUID 幂等键；任务和采购记录行锁保护状态检查；审批决定不可变；业务决策先提交，再通过可重放恢复事件推进 graph；并发测试确认同一任务仅一个决策成功。
- 权限与审计：指定审批人才能查看和处理任务，申请人自审返回 `SELF_APPROVAL_FORBIDDEN`；驳回必须填写理由；提交、取消、批准和驳回写入只追加审计事件。
- 前端：新增待办/已处理审批中心、审批详情和管理员规则页；采购详情支持审批链预览、显式确认提交、草稿取消、工作流进度及审计时间线；APPROVER/ADMIN 路由与导航按角色隔离。
- 后端：主机 Conda 环境与容器内 `ruff check .` 均通过；连接 Compose PostgreSQL 的全量 `pytest` 为 35 passed；Alembic 为 `20261022_0005 (head)` 且 schema 无漂移，第三方 checkpoint 表由 saver 自主管理。
- 前端：`npm run lint`、`npm run typecheck`、`npm test`、`npm run build` 通过；4 个 Vitest 文件、7 项测试通过；`npm audit` 为 0 vulnerabilities。
- 运行验收：PostgreSQL、FastAPI、Vue/Nginx 三服务均 healthy；`/healthz`、`/readyz` 和前端代理返回 200 及版本 `0.5.0`。真实 HTTP 完成 60000 元两级提交、逐级恢复和最终批准，浏览器完成审批与规则页面及 390px 响应式检查，控制台无错误。
- 范围控制：未实现采购履约状态转换、MCP Server/Client、Mini Agent Harness 或技术观察页面，M5-M6 仍保持 NOT_STARTED。

## M5 验收记录（2026-10-22）

- MCP：基于官方 Python SDK 的独立 stdio Server/Client 可完成初始化握手、工具发现与调用；Server 仅暴露 `inventory_search`、`supplier_quote` 两个只读工具，库存和报价查询复用参数化 SQLAlchemy 服务。
- 工具治理：统一注册表同时管理 M3 本地工具与 MCP 工具，执行前校验 Pydantic 输入、角色、启用状态、只读属性和数据库策略；非白名单调用返回 `TOOL_NOT_ALLOWED`，技术管理员不能借工具执行审批。
- Mini Agent Harness：`AgentRunner` 强制总超时、单工具超时、最大步骤数、每工具调用上限和有限重试；步骤、重试、错误码及脱敏输入/输出摘要持久化，敏感键和常见令牌格式不会写入轨迹。
- 可观测性：新增运行列表/详情、步骤查询和支持 `Last-Event-ID` 的持久化 SSE；M4 审批工作流也可按真实持久化步骤回放节点状态，不使用仅存在于前端的模拟轨迹。
- 前端：新增 Workflow 运行列表与节点图、MCP Server/工具中心、Harness 运行列表与步骤检查器；路由和导航仅向 `ADMIN`、`TECH_ADMIN` 开放。
- 后端：主机 Conda 环境与容器内 `ruff check .` 均通过；连接现有 Compose PostgreSQL 的全量 `pytest` 为 39 passed，M5 定向测试为 4 passed；Alembic 为 `20261022_0006 (head)` 且 schema 无漂移。
- 前端：`npm run lint`、`npm run typecheck`、`npm test -- --run`、`npm run build` 通过；5 个 Vitest 文件、8 项测试通过；`npm audit` 为 0 vulnerabilities。
- 运行验收：未重建已有 PostgreSQL 容器，仅重建 API 与前端服务；三服务均 healthy，`/healthz`、`/readyz` 和前端代理返回 200 及版本 `0.6.0`。真实 HTTP 验证 MCP 调用、轨迹、SSE 续传、白名单拒绝及技术管理员审批 403。
- 浏览器验收：完成工具发现与只读试运行、Harness 步骤详情、Workflow 真实节点图检查；390×844 视口无横向溢出，控制台无错误或警告。
- 范围控制：未实现采购履约、收货、关闭、生产 ERP 连接或远程 MCP 鉴权；上述能力保持为 M6 范围。

## M6 验收记录（2026-10-22）

- 全链路：新增严格的 DEMO 履约状态机 `APPROVED → ORDERED → RECEIVED → CLOSED`；仅 `PROCUREMENT` 可写，要求最新版本和 UUID 幂等键，每次转换与幂等记录、审计事件在同一事务提交。
- 权限与契约：未批准、跳步、旧版本、同键异载荷均被拒绝；员工、`ADMIN`、`TECH_ADMIN` 不能推进履约；OpenAPI 请求模型、401/403 及不存在任意 shell/SQL 执行路由均有自动化检查。
- 运行事件：普通聊天 run 独立标记为 `CHAT`，消息发送持久化 run、step 和 5 个 SSE 事件；`Last-Event-ID` 续传只读且不会重复业务写入。Alembic 增量迁移为 `20261022_0007 (head)`，schema 无漂移。
- 前端：采购角色可查看已批准与履约中申请，详情展示四步 DEMO 进度与显式确认；申请人只读。助手展示真实持久化运行事件，移动端 Grid 最小宽度已约束。
- 后端：主机 Conda 环境与容器内 `ruff check .` 均通过；连接现有 Compose PostgreSQL 的全量 `pytest -q` 均为 46 passed，仅有 Starlette TestClient 的上游 AnyIO 弃用提示。
- 前端：`npm run lint`、`npm run typecheck`、`npm test -- --run`、`npm run build` 通过；7 个 Vitest 文件、11 项测试通过；完整 `npm audit` 为 0 vulnerabilities。
- 部署与性能：未重建 PostgreSQL 容器，仅重建 API/前端；三服务 healthy，版本 `0.7.0`。只读 smoke 40 次请求 0 错误，p95 为 2.79 ms，健康、就绪、401 与安全路由检查通过。
- 浏览器：1440、1280、1024、390 px 均无横向溢出；聊天事件流展示 5 个持久化事件，履约列表、详情和确认弹窗可用，控制台无错误或警告。
- 日志与手册：新增账号/权限/操作手册；API 输出脱敏单行 JSON 请求日志，并以 `request_id` 关联响应、业务审计和运行轨迹；容器关闭原始 URL access log。
- 范围边界：所有库存、报价和履约均明确为 Mock/DEMO；没有连接真实 ERP、供应商、支付或物流，也不声称生产级高可用或容量指标。
