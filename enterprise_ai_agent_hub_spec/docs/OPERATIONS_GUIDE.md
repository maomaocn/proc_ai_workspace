# M6 本地操作手册

## 1. 适用范围

本手册面向本地教学和验收环境。库存、报价、下单、收货和关闭均为 DEMO 数据或本地状态，
不代表生产 ERP、真实供应商、支付或物流操作。

## 2. 启动与检查

```bash
cp .env.example .env             # 已有 .env 时不要覆盖
POSTGRES_PORT=55432 APP_VERSION=0.7.0 docker compose up --build -d
docker compose ps
curl --fail http://localhost:8000/healthz
curl --fail http://localhost:8000/readyz
curl --fail http://localhost:5173/api/readyz
```

前端、API 和 OpenAPI 分别位于 `http://localhost:5173`、`http://localhost:8000` 和
`http://localhost:8000/docs`。默认 Mock LLM/Embedding 无需 API Key。

## 3. 迁移与 Seed

API 启动脚本先执行 `alembic upgrade head`，再在非生产环境执行幂等 seed。当前项目迁移应为
`20261022_0007 (head)`；M6 复用已有状态、幂等和审计结构，并通过增量迁移将普通聊天
运行与 Harness 运行明确区分。迁移只替换 `agent_runs.run_type` 检查约束，不删除业务数据。

```bash
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose exec -T api python -m app.db.seed
```

Seed 只补充缺失的演示账号和数据，不清空现有记录。生产环境必须设置
`SEED_DEMO_DATA=false` 并替换 `JWT_SECRET_KEY`。

## 4. 质量与交付验收

```bash
docker compose exec -T api ruff check .
docker compose exec -T api pytest -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend audit
conda run -n proc_ai_workspace python scripts/m6_smoke.py --requests 40
```

冒烟脚本只执行健康、OpenAPI、401 和授权 GET 请求，不创建或修改采购数据。

## 5. 日常运维

```bash
docker compose logs --tail=200 api
docker compose logs --tail=200 frontend
docker compose logs --tail=200 db
docker compose restart api frontend
docker compose down              # 保留数据卷
```

API 应用日志使用单行 JSON，包含 `request_id`、路由模板、状态码、耗时及鉴权后的用户 UUID/
角色。日志不记录请求体、查询参数、Authorization、Cookie、对话内容、文档正文或 API Key。
容器已关闭会记录原始 URL 的 Uvicorn access log；响应头 `X-Request-ID` 可用于关联 JSON
日志和数据库 `audit_events`。

不要执行 `docker compose down -v`，除非明确决定删除本地数据库、上传文件和 Chroma 数据。
升级前可使用 PostgreSQL 工具备份：

```bash
docker compose exec -T db pg_dump -U app -d enterprise_ai_agent_hub -Fc > local-backup.dump
```

本项目不承诺生产级高可用。应用回退前必须先确认旧版本能够读取当前 schema；禁止以删除表、
清空数据卷或强制降级迁移作为常规回退手段。

## 6. 安全边界

- `.env`、真实 API Key、生产账号和数据库备份不得提交 Git。
- `TECH_ADMIN` 只能观察技术运行并试用白名单只读 MCP 工具。
- `ADMIN` 不能审批或推进采购履约；履约写入仅允许 `PROCUREMENT`。
- 写接口不自动重试；客户端复用原 `Idempotency-Key` 查询同一操作结果。
- MCP、LLM、RAG 和用户输入均视为不可信数据，不能改变后端权限或状态机。

账号、角色矩阵和各角色操作流程见 `USER_GUIDE.md`。

