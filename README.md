# Enterprise AI Agent Hub

Enterprise AI Agent Hub 是一个分阶段实施的企业级 AI 智能采购与办公协同教学项目。
当前仓库完成
[V1.1 实施计划](enterprise_ai_agent_hub_spec/docs/IMPLEMENTATION_PLAN.md)的
**M0：工程骨架与本地环境**、**M1：身份、会话与 LLM 意图解析**和
**M2：企业知识库与 RAG**。

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

M2 不创建或提交采购申请，也不包含库存报价、Tool Calling、审批、LangGraph、MCP
或 Harness；这些功能按 M3-M6 逐步实现。

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
避免容器误将 `localhost` 当作 PostgreSQL 服务。

`.env` 已被 Git 忽略。不得提交 API Key、密码或其他真实密钥。

## 数据库迁移与初始化

API 容器启动时执行：

```bash
alembic upgrade head
```

M1 迁移新增部门、用户、多角色、会话和消息表；M2 迁移新增知识库、ACL、文档和分块
表。启动脚本在非生产环境执行幂等
演示 seed；它只补充缺失记录，不清空或覆盖已有用户。生产环境必须设置
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
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

## 本地演示账号

以下账号由本地 seed 命令创建，仅用于 Mock 演示：

| 用户名 | 初始密码 | 部门 | 角色与用途 |
|---|---|---|---|
| `employee` | `DemoPass123!` | 研发部 | EMPLOYEE，普通员工采购对话 |
| `approver` | `DemoPass123!` | 财务部 | EMPLOYEE、APPROVER，后续审批演示 |
| `procurement` | `DemoPass123!` | 采购部 | EMPLOYEE、PROCUREMENT，后续采购执行演示 |
| `admin` | `DemoPass123!` | 信息技术部 | EMPLOYEE、ADMIN，业务管理接口验收 |
| `techadmin` | `DemoPass123!` | 信息技术部 | TECH_ADMIN，技术运维权限隔离验收 |

- 前端登录页：<http://localhost:5173/login>
- 登录接口：`POST /api/v1/auth/login`
- 首次体验建议使用 `employee`。

这些是公开的本地演示凭据。生产环境禁止启用 `SEED_DEMO_DATA`，也不得沿用上述密码。

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

也可以使用项目内虚拟环境：

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
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
├── docs/           # 里程碑补充文档
├── sample_data/    # 可审查的制度、库存与报价演示数据
├── enterprise_ai_agent_hub_spec/  # 权威需求文件
├── .env.example
└── compose.yaml
```

## M2 验收

```bash
docker compose config
POSTGRES_PORT=55432 docker compose up --build -d
curl --fail http://localhost:8000/healthz
curl --fail http://localhost:8000/readyz
POSTGRES_PORT=55432 docker compose exec api ruff check .
POSTGRES_PORT=55432 docker compose exec api pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit
```

验收栈保持运行时可直接访问前端进行登录和意图确认。使用 `55432` 是为了避免与
宿主机已有 PostgreSQL 冲突；停止时执行 `POSTGRES_PORT=55432 docker compose down`，
不要添加 `-v`，以保留数据库卷。
