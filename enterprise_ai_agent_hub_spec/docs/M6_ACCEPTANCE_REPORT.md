# M6 验收报告

## 1. 验收范围

- 版本：`0.7.0`
- 模式：本地 Mock/DEMO；不依赖真实 LLM、Embedding、ERP、供应商、支付或物流服务
- 数据库：现有 PostgreSQL 16 容器，执行增量 Alembic 迁移，不重建容器、不清空数据
- 主链路：需求解析、知识检索、库存/报价、采购草稿、两级审批、模拟履约、审计与运行事件

## 2. AC-01 至 AC-20

| ID | 结果 | 验收证据 |
|---|---|---|
| AC-01 | PASS | API 测试覆盖未登录和非法 token 401、越权 403；JWT 过期校验由认证测试覆盖。 |
| AC-02 | PASS | 所有权、会话与知识 ACL 测试通过；员工不能查看他人资源，`TECH_ADMIN` 审批和履约均为 403。 |
| AC-03 | PASS | Mock 解析“采购10台笔记本，每台6000元”为数量 10、单价 6000.00，缺用途时返回追问。 |
| AC-04 | PASS | 未确认只持久化会话消息；确认接口服务端校验必填字段并幂等创建一个草稿。 |
| AC-05 | PASS | 文档测试覆盖 TXT/MD/PDF 文本层、READY、SHA-256 去重、非法类型、空文件与大小限制。 |
| AC-06 | PASS | RAG 返回真实片段、文件名和页码；无依据固定拒答；READY 与 ACL 在查询后再次过滤。 |
| AC-07 | PASS | Pydantic 参数校验、工具角色白名单和超时生效；库存、报价标记为数据库 DEMO 数据。 |
| AC-08 | PASS | 金额使用 PostgreSQL `NUMERIC(14,2)` 和 Python `Decimal`；10×6000.00 为 60000.00。 |
| AC-09 | PASS | 规则测试覆盖不高于 10000 元一级、高于 10000 元两级及规则缺失/重叠/级别缺口。 |
| AC-10 | PASS | 两级顺序审批、未审批状态、自审拒绝、驳回理由、指定审批人权限均有集成测试。 |
| AC-11 | PASS | 审批与履约均覆盖同键重放、同键异载荷 409；审批并发只允许一个决策成功。 |
| AC-12 | PASS | `test_m6_e2e.py` 覆盖未批准拒绝、不可跳步、版本冲突、`APPROVED→ORDERED→RECEIVED→CLOSED` 和三条审计。 |
| AC-13 | PASS | 聊天、Workflow 与 Harness 使用持久化事件；SSE 包含运行/节点/文本事件，`Last-Event-ID` 续传不重复写消息。 |
| AC-14 | PASS | Workflow 页面读取真实 `agent_runs`/`agent_steps`，历史运行可查询，暂停与恢复步骤来自 LangGraph 数据。 |
| AC-15 | PASS | 官方 MCP SDK stdio Client/Server 完成握手、发现和只读库存查询；未授权工具由注册表拒绝。 |
| AC-16 | PASS | Harness 运行和步骤可查；总超时、单工具超时、步数/调用次数、重试和脱敏有自动化测试。 |
| AC-17 | PASS | 浏览器在 1440、1280、1024、390 px 检查，无横向溢出、控制台错误或业务内容照搬。 |
| AC-18 | PASS | 关键视图具备加载、空、错误、成功、分页、表单校验、显式确认和可见焦点状态；组件测试通过。 |
| AC-19 | PASS | OpenAPI 和 smoke 校验无 shell/SQL 执行路由；JWT、ACL、工具策略独立于提示词；提交文件无密钥。 |
| AC-20 | PASS | 默认 Mock 配置无 Key 可运行；Compose 健康、迁移到 `20261022_0007`、seed 幂等、全链路 E2E 通过。 |

P0 项全部通过；P1 的 AC-14、AC-15、AC-16 均有可查询数据、自动化测试和浏览器证据。

## 3. 自动化与运行证据

```bash
conda run -n proc_ai_workspace ruff check .
RUN_DB_TESTS=true DATABASE_URL=postgresql+asyncpg://app:app@localhost:55432/enterprise_ai_agent_hub \
  CHECKPOINT_DATABASE_URL=postgresql://app:app@localhost:55432/enterprise_ai_agent_hub pytest -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend audit
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose exec -T api ruff check .
docker compose exec -T api pytest -q
conda run -n proc_ai_workspace python scripts/m6_smoke.py --requests 40
```

最终执行记录：后端 46 项、前端 11 项测试通过；Ruff、ESLint、TypeScript、Vite 构建、
`npm audit`、容器内检查与 Alembic schema 漂移检查通过。只读 smoke 连续 40 次授权 GET
无错误，p95 为 2.79 ms，远低于 1500 ms 门限。浏览器完成四档宽度和最新聊天事件流检查。

补充交付检查验证了 JSON 请求日志、`X-Request-ID` 关联、路由模板记录和查询参数排除；容器
关闭原始 URL access log，避免 token 等查询参数被重复日志记录。

金额派生回归覆盖确认场景：数量 10、单价上限由 6000 改为 9000 时，即使请求仍携带旧派生值
60000.00，服务端也会按最终数量与单价归一化为 90000.00；前端同步自动重算只读总预算。

## 4. 已知限制

- 履约只改变本地状态并写审计，不创建真实订单、不支付、不调用 ERP、物流或供应商。
- Mock LLM 和 Embedding 用于确定性演示，不代表生产模型质量、吞吐或费用。
- PDF 仅处理文本层，不提供 OCR；MCP 仅为本地 stdio，不包含生产远程鉴权与高可用。
- 性能检查是单机、本地、只读 API 冒烟，不是容量测试或生产 SLO 证明。
- Starlette TestClient 仍有上游 AnyIO 弃用提示，不影响当前测试结果。

## 5. 交付文档

- `OPERATIONS_GUIDE.md`：启动、迁移、seed、检查、备份和安全边界
- `USER_GUIDE.md`：演示账号、角色权限矩阵、各角色操作流程和日志说明
- `DEMO_SCRIPT.md`：业务主链路、技术链路和失败分支
- `TROUBLESHOOTING.md`：常见启动、迁移、SSE、MCP 和权限问题
