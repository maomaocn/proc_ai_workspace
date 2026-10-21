# Enterprise AI Agent Hub

Enterprise AI Agent Hub 是一个分阶段实施的企业级 AI 智能采购与办公协同教学项目。
当前仓库完成
[V1.1 实施计划](enterprise_ai_agent_hub_spec/docs/IMPLEMENTATION_PLAN.md)的
**M0：工程骨架与本地环境**。

需求入口位于 [`enterprise_ai_agent_hub_spec/README.md`](enterprise_ai_agent_hub_spec/README.md)，
阶段验收状态记录在
[`docs/PHASE_STATUS.md`](enterprise_ai_agent_hub_spec/docs/PHASE_STATUS.md)。

## M0 已包含

- Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2 和 Alembic
- PostgreSQL 16 与 Docker Compose
- Vue 3、Vite 和 TypeScript 状态工作台
- 默认 Mock 模型与 Mock Embedding 配置，不需要真实 API Key
- `/healthz` 存活检查、`/readyz` PostgreSQL 就绪检查和 OpenAPI 文档
- Pytest、Ruff、ESLint、Vue TSC 和前端构建命令

M0 不包含用户、采购、RAG、Agent、MCP 或审批业务；这些功能按 M1-M6 逐步实现。

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

停止服务但保留数据库卷：

```bash
docker compose down
```

不要使用 `docker compose down -v`，除非明确希望删除本地 PostgreSQL 数据。

## 环境变量

复制示例配置仅用于覆盖默认值：

```bash
cp .env.example .env
```

默认值为 `MODEL_PROVIDER=mock` 和 `EMBEDDING_PROVIDER=mock`。可选远程 Provider
变量目前只作为后续里程碑的安全配置入口，M0 不会调用任何模型服务。
`DATABASE_URL` 用于本地 Python/Conda，`COMPOSE_DATABASE_URL` 用于 API 容器，
避免容器误将 `localhost` 当作 PostgreSQL 服务。

`.env` 已被 Git 忽略。不得提交 API Key、密码或其他真实密钥。

## 数据库迁移与初始化

API 容器启动时执行：

```bash
alembic upgrade head
```

M0 的迁移只建立 Alembic 基线，不创建 M1-M6 的业务表，也没有种子业务数据。
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

测试通过依赖覆盖验证 `/readyz` 的成功和失败响应，不要求本机安装 PostgreSQL。

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
npm run build
```

## 目录

```text
.
├── backend/        # FastAPI、数据库连接、Alembic 和测试
├── frontend/       # Vue 3 状态工作台
├── docs/           # 里程碑补充文档
├── sample_data/    # 后续里程碑的可审查演示数据
├── enterprise_ai_agent_hub_spec/  # 权威需求文件
├── .env.example
└── compose.yaml
```

## M0 验收

```bash
docker compose config
POSTGRES_PORT=55432 docker compose up --build -d
curl --fail http://localhost:8000/healthz
curl --fail http://localhost:8000/readyz
POSTGRES_PORT=55432 docker compose exec api ruff check .
POSTGRES_PORT=55432 docker compose exec api pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
POSTGRES_PORT=55432 docker compose down
```

上例使用 `55432` 是为了避免与宿主机已有 PostgreSQL 冲突；未占用 `5432` 时可省略该环境变量。
