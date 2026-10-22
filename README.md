# Enterprise AI Agent Hub

Enterprise AI Agent Hub 是一个分阶段实施的企业级 AI 智能采购与办公协同教学项目。
当前仓库完成
[V1.1 实施计划](enterprise_ai_agent_hub_spec/docs/IMPLEMENTATION_PLAN.md)的
**M0：工程骨架与本地环境**、**M1：身份、会话与 LLM 意图解析**和
**M2：企业知识库与 RAG**、**M3：采购业务与 Tool Calling**、
**M4：LangGraph 工作流与人工审批**、**M5：MCP 与 Mini Agent Harness**和
**M6：全链路验收与交付**。

需求入口位于 [`enterprise_ai_agent_hub_spec/README.md`](enterprise_ai_agent_hub_spec/README.md)，
阶段验收状态记录在
[`docs/PHASE_STATUS.md`](enterprise_ai_agent_hub_spec/docs/PHASE_STATUS.md)。

## 当前能力

- Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2 和 Alembic
- PostgreSQL 16 与 Docker Compose
- Vue 3、Vite 和 TypeScript 状态工作台
- 默认 Mock 模型与 Mock Embedding 配置，不需要真实 API Key
- `/healthz` 存活检查、`/readyz` PostgreSQL 就绪检查和 OpenAPI 文档
- Pytest、Ruff、ESLint、Vue TSC 和前端构建命令
- Argon2 密码哈希、JWT 登录、多角色 RBAC 与管理员用户 API
- PostgreSQL 会话/消息持久化和会话所有权隔离
- 可复现 Mock LLM 与 OpenAI-compatible 意图解析适配器
- 严格的 `PurchaseIntent`、缺字段追问和服务端确认状态
- Vue 登录、工作台、采购助手和可编辑结构化意图卡
- 知识库 ACL、PDF/TXT/MD 上传校验、SHA-256 去重、解析和分块
- 默认可复现 Mock Embedding、持久化 Chroma 检索和真实来源引用
- 知识库文档列表、详情、上传、重建索引、删除及检索测试页面
- 库存、供应商、DEMO 报价、采购草稿和候选方案数据模型及 API
- 服务端 `Decimal` 金额计算、草稿版本冲突检查和资源所有权隔离
- 只读 Tool Registry：`inventory.search`、`supplier.quote`、`policy.search`
- 采购列表、新建、详情/编辑、方案生成、库存和供应商报价页面
- 数据库金额规则、一至多级顺序审批、禁止自审和驳回理由校验
- LangGraph `interrupt`/`Command(resume=...)` 与 PostgreSQL 持久化 checkpoint
- 提交、取消和审批决策幂等；行锁保护并发决策；只追加审计事件
- 我的审批、审批详情、申请审批进度和管理员审批规则页面
- 独立本地 stdio MCP Server/Client、服务端身份校验和工具发现
- 经 MCP 查询演示库存与供应商报价，统一只读 Tool Registry
- Mini Agent Harness 白名单、步数/调用/总时长限制、只读有限重试与稳定错误码
- 持久化 run/step/SSE 事件追踪、敏感参数脱敏和 Last-Event-ID 续读
- Workflow 节点图、MCP 工具中心和 Harness 运行中心
- `APPROVED → ORDERED → RECEIVED → CLOSED` 模拟采购履约状态机
- 履约角色隔离、版本冲突、幂等重放和只追加审计
- AC-01～AC-20 验收矩阵、操作手册、演示脚本及安全/性能冒烟
- 带 request ID、路由、状态、耗时和角色的脱敏 JSON 应用日志

项目不会连接真实采购平台、支付系统或生产 ERP，也不提供任意 Shell、SQL 或文件写入工具。
`ORDERED/RECEIVED/CLOSED` 仅代表本地 DEMO 状态。

## 环境要求

- Docker Desktop 或兼容的 Docker Engine，支持 Docker Compose
- 可选本地开发：Python 3.12、Node.js 22、npm 10+

## 使用 Docker Compose 启动

默认配置可直接启动，无需创建 `.env`，也无需 LLM API Key：

```bash
docker compose up --build
```

如果宿主机的 PostgreSQL 已占用 5432，可只覆盖对外端口，不影响容器内连接：

```bash
POSTGRES_PORT=55432 docker compose up --build
```

服务地址：

- 前端工作台：<http://localhost:5173>
- API：<http://localhost:8000>
- OpenAPI：<http://localhost:8000/docs>
- PostgreSQL：默认 `localhost:5432`；使用上面的端口覆盖时为 `localhost:55432`

检查服务：

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
docker compose ps
```

停止服务但保留 PostgreSQL、上传文档和 Chroma 数据卷：

```bash
docker compose down
```

不要使用 `docker compose down -v`，除非明确希望删除本地 PostgreSQL、上传文档和
Chroma 索引数据。

## 环境变量

复制示例配置仅用于覆盖默认值：

```bash
cp .env.example .env
```

默认值为 `MODEL_PROVIDER=mock` 和 `EMBEDDING_PROVIDER=mock`。Mock 意图解析无需
任何 API Key 且结果可复现；Mock Embedding 使用确定性词项哈希向量，不使用随机向量
冒充语义结果。切换 `openai_compatible` 或远程 Embedding 时才读取对应 URL、模型和 Key。
`DATABASE_URL` 用于本地 Python/Conda，`COMPOSE_DATABASE_URL` 用于 API 容器，
避免容器误将 `localhost` 当作 PostgreSQL 服务。LangGraph 官方 PostgreSQL saver 使用
psycopg 连接，因此分别使用 `CHECKPOINT_DATABASE_URL` 和
`COMPOSE_CHECKPOINT_DATABASE_URL`，URL 不含 `+asyncpg`。

`.env` 已被 Git 忽略。不得提交 API Key、密码或其他真实密钥。

## 数据库迁移与初始化

API 容器启动时执行：

```bash
alembic upgrade head
```

M1 迁移新增部门、用户、多角色、会话和消息表；M2 迁移新增知识库、ACL、文档和分块
表；M3 迁移新增库存、供应商、报价、采购申请和候选方案表；M4 迁移新增审批规则、任务、
不可变决策、工作流运行/步骤、审计、幂等和恢复事件表；M5 迁移新增 MCP 服务、工具策略
和持久化运行事件，并扩展运行限额与步骤结束时间。LangGraph saver 自主管理四张
`checkpoint_*` 表，Alembic 明确忽略这些第三方表。启动脚本在非生产环境执行幂等演示
seed；它只补充缺失记录，不清空或覆盖已有用户。生产环境必须设置
`SEED_DEMO_DATA=false` 并替换 `JWT_SECRET_KEY`。
进入后端目录后可手动检查迁移：

```bash
cd backend
alembic current
alembic upgrade head
```

## 本地后端开发

以下命令要求 Python 3.12 和一个可访问的 PostgreSQL：

使用已有的 Conda 环境：

```bash
conda activate proc_ai_workspace
python --version
python -m pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/enterprise_ai_agent_hub
export CHECKPOINT_DATABASE_URL=postgresql://app:app@localhost:5432/enterprise_ai_agent_hub
cd backend
alembic upgrade head
uvicorn app.main:app --reload --no-access-log
```

## 本地演示账号

以下账号由本地 seed 命令创建，仅用于 Mock 演示：

| 用户名 | 初始密码 | 部门 | 角色与用途 |
|---|---|---|---|
| `employee` | `DemoPass123!` | 研发部 | EMPLOYEE，普通员工采购对话 |
| `manager` | `DemoPass123!` | 研发部 | EMPLOYEE、APPROVER，部门一级审批 |
| `approver` | `DemoPass123!` | 财务部 | EMPLOYEE、APPROVER，财务二级审批 |
| `procurement` | `DemoPass123!` | 采购部 | EMPLOYEE、PROCUREMENT，后续采购执行演示 |
| `admin` | `DemoPass123!` | 信息技术部 | EMPLOYEE、ADMIN，业务管理接口验收 |
| `techadmin` | `DemoPass123!` | 信息技术部 | TECH_ADMIN，技术运维权限隔离验收 |

- 前端登录页：<http://localhost:5173/login>
- 登录接口：`POST /api/v1/auth/login`
- 首次体验建议使用 `employee`。

这些是公开的本地演示凭据。生产环境禁止启用 `SEED_DEMO_DATA`，也不得沿用上述密码。

本地 PostgreSQL 演示连接默认使用与 Compose 一致的公开开发凭据：数据库
`enterprise_ai_agent_hub`、用户 `app`、密码 `app`。使用本仓库 `.env` 的 55432 端口时可登录：

```bash
psql -h localhost -p 55432 -U app -d enterprise_ai_agent_hub
# Password: app
```

## M2 知识库演示

Seed 会创建“企业采购制度”知识库，并向 `EMPLOYEE` 角色授予只读权限。管理员负责上传、
重建和删除，普通员工只能查看和检索。示例文件位于：

```text
enterprise_ai_agent_hub_spec/sample_data/policies/采购管理制度.md
```

演示步骤：

1. 使用 `admin / DemoPass123!` 登录，在“企业知识库”中上传示例制度。
2. 使用 `employee / DemoPass123!` 登录，检索“笔记本超过一万元需要几级审批？”。
3. 结果应返回真实文件名、片段、页码和分数；无关问题应显示“当前知识库未检索到足够依据”。

上传仅支持文本型 PDF、UTF-8 TXT 和 MD，单文件默认最大 20MB。扫描 PDF 的 OCR 不在
M2 范围内。上传内容保存在 `knowledge_uploads` 卷，向量保存在 `chroma_data` 卷；文档
软删除后立即从检索中过滤，并同步清理对应向量和上传文件。

## M3 采购与工具演示

Seed 会幂等创建 3 个库存商品、2 个 DEMO 供应商和 4 条 DEMO 报价。演示数据只用于
本地验收，不代表实时库存或市场价格：

- `employee`：创建、编辑本人采购草稿并生成候选方案；确认对话意图后也会创建草稿。
- `procurement`：查看和维护供应商与 DEMO 报价。
- `admin`：查看全部采购草稿并维护库存、供应商与报价。
- `techadmin`：不自动获得业务工具或供应商数据权限，用于验证职责隔离。

推荐流程：

1. 使用 `employee / DemoPass123!` 登录，打开“采购申请”并新建 10 台、单价上限
   6000 元的笔记本草稿；服务端应返回总预算 `60000.00`。
2. 在详情页生成候选方案，查看库存、DEMO 报价、风险标记、只读工具轨迹和制度引用。
3. 使用 `procurement / DemoPass123!` 登录“供应商报价”，查看或补充本地 DEMO 报价。

工具输入先经过 Pydantic schema 校验，再检查角色白名单和超时；M3 注册表只接受只读工具。
采购金额由后端 PostgreSQL `NUMERIC(14,2)` 与 Python `Decimal` 计算，前端只负责展示。

## M4 审批工作流演示

Seed 会创建以下确定性金额规则：总预算不超过 `10000.00` 元时由申请人所在部门负责人
一级审批；超过 `10000.00` 元时依次经过部门负责人和财务审批。审批人必须是启用状态的
`APPROVER`，申请人永远不会被分配为自己的审批人。

推荐流程：

1. 使用 `employee / DemoPass123!` 创建 10 台笔记本草稿并生成候选方案；打开提交确认框，
   检查审批链为 `manager -> approver` 后提交。
2. 使用 `manager / DemoPass123!` 打开“我的审批”批准第一级。采购状态仍应为
   `PENDING_APPROVAL`，LangGraph 从 PostgreSQL checkpoint 恢复后等待第二级。
3. 使用 `approver / DemoPass123!` 批准第二级；申请最终变为 `APPROVED`。审批详情和采购
   详情显示处理人、意见、工作流 run/thread 标识及审计事件。
4. 使用 `admin / DemoPass123!` 打开“审批规则”查看或配置金额规则。停用必要规则会让新
   提交在服务端明确失败，不会绕过规则自动批准。

低于等于一万元的申请只有一级；驳回必须输入至少 5 个字符。提交、取消和决策 API 都要求
UUID 格式的 `Idempotency-Key`。同一键、同一请求安全重放；同一键用于不同负载返回 409。
审批决定先在业务事务中持久化，再通过可重放恢复事件推进 LangGraph。

## M5 MCP 与 Harness 演示

MCP Server 是由 API 通过 stdio 启动的独立 Python 子进程，注册名为
`enterprise-ai-agent-hub-mcp`。它只暴露 `inventory_search` 和 `supplier_quote`，查询本地
PostgreSQL 演示数据；不需要 LLM API Key，也不提供任意 SQL、Shell 或文件系统写入能力。

推荐流程：

1. 使用 `techadmin / DemoPass123!` 登录，打开“MCP 工具中心”，确认 Server 为
   `HEALTHY`、传输类型为 `STDIO`，并可发现两个只读工具。
2. 选择 `mcp.inventory.search`，保留默认 JSON 参数执行测试；结果应标记
   `MCP_STDIO`，并返回 DEMO 库存及新的 Harness `run_id`。
3. 打开该 run，检查步骤、工具耗时、调用次数、重试、错误码和脱敏摘要；运行事件 API
   `GET /api/v1/agent-runs/{run_id}/events` 支持 `Last-Event-ID` 续读。
4. 打开“Workflow 运行”，选择 M4 审批 run，节点图应显示真实
   `resolve_approval_chain -> await_approval_stage_*` 路径及等待/完成状态。

默认限制为最大 12 步、总执行 90 秒、单工具 5 秒、只读工具最多 2 次尝试；关键失败码为
`STEP_LIMIT_EXCEEDED`、`TOOL_TIMEOUT`、`TOOL_NOT_ALLOWED` 和 `RUN_TIMEOUT`。工具策略保存在
`tool_policies`，拒绝优先；技术角色可观察和测试只读 MCP 工具，但不会因此获得审批权限。

也可在后端目录直接验证 MCP 握手与发现：

```bash
cd backend
python -m app.mcp.server
# Server 使用 stdio 协议，正常等待客户端 JSON-RPC 输入，不提供 HTTP 端口。
```

## M6 履约与交付演示

只有 `PROCUREMENT` 角色可以推进已批准申请，且必须严格按
`APPROVED → ORDERED → RECEIVED → CLOSED` 顺序执行。每次请求要求当前 `version` 和 UUID
格式的 `Idempotency-Key`；同键同负载返回原结果，同键不同负载返回 409。`ADMIN` 和
`TECH_ADMIN` 均不能代替采购人员执行履约。

推荐流程：

1. 按 M4 流程将 10 台笔记本申请审批到 `APPROVED`。
2. 使用 `procurement / DemoPass123!` 登录，在“采购申请与履约”中打开该申请。
3. 依次确认模拟下单、模拟收货和关闭；每一步都应增加版本并写入审计时间线。
4. 切回 `employee`，确认同一采购申请显示最终 `CLOSED` 状态。

完整材料：

- [系统使用与权限手册](enterprise_ai_agent_hub_spec/docs/USER_GUIDE.md)
- [操作手册](enterprise_ai_agent_hub_spec/docs/OPERATIONS_GUIDE.md)
- [演示脚本](enterprise_ai_agent_hub_spec/docs/DEMO_SCRIPT.md)
- [故障排查](enterprise_ai_agent_hub_spec/docs/TROUBLESHOOTING.md)
- [M6 验收报告](enterprise_ai_agent_hub_spec/docs/M6_ACCEPTANCE_REPORT.md)

真实服务启动后可执行只读安全与性能冒烟：

```bash
conda run -n proc_ai_workspace python scripts/m6_smoke.py \
  --base-url http://localhost:8000 --requests 40
```

也可以使用项目内虚拟环境：

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --no-access-log
```

运行质量检查：

```bash
cd backend
ruff check .
pytest
```

默认测试包含单元测试；PostgreSQL 集成测试使用本项目的 `55432` 验收数据库：

```bash
RUN_DB_TESTS=true \
DATABASE_URL=postgresql+asyncpg://app:app@localhost:55432/enterprise_ai_agent_hub \
pytest
```

## 本地前端开发

```bash
cd frontend
npm ci
npm run dev
```

Vite 开发服务器默认访问 `http://localhost:5173`，并将 `/api` 请求代理到
`http://localhost:8000`。质量检查：

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

## 目录

```text
.
├── backend/        # FastAPI、数据库、RAG、Chroma 适配和测试
├── frontend/       # Vue 3 状态工作台
├── scripts/        # 部署、安全和性能冒烟脚本
├── sample_data/    # 可审查的制度、库存与报价演示数据
├── enterprise_ai_agent_hub_spec/  # 权威需求文件
├── .env.example
└── compose.yaml
```

## M6 验收

```bash
docker compose config
POSTGRES_PORT=55432 docker compose up --build -d
curl --fail http://localhost:8000/healthz
curl --fail http://localhost:8000/readyz
POSTGRES_PORT=55432 docker compose exec api ruff check .
POSTGRES_PORT=55432 docker compose exec api alembic current
POSTGRES_PORT=55432 docker compose exec api alembic check
POSTGRES_PORT=55432 docker compose exec -e RUN_DB_TESTS=true api pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit
```

M6 自动化在既有测试基础上覆盖员工发起、方案、两级审批、采购履约到关闭，以及未批准拒绝、
非法跳转、角色越权、版本冲突、幂等重放/冲突和 OpenAPI 契约。完整通过标准和实际结果见
M6 验收报告。

验收栈保持运行时可直接访问前端进行登录和意图确认。使用 `55432` 是为了避免与
宿主机已有 PostgreSQL 冲突；停止时执行 `POSTGRES_PORT=55432 docker compose down`，
不要添加 `-v`，以保留数据库卷。
