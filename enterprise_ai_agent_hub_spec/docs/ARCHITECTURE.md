# 技术架构与工程规格 V1.1

## 1. 技术选型

- Python 3.12；FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic。
- PostgreSQL 16（业务数据）；Chroma（本地向量检索，MVP）；本地文件目录（上传文档）；可选 Redis（MVP 不强依赖）。
- LangGraph（状态机、检查点、人工审批恢复）；模型 SDK 通过适配层封装，支持 Mock 和 OpenAI-compatible API。
- MCP Python SDK（独立的本地 MCP Server 与 Client；优先 stdio 传输以降低教学环境复杂度）。
- 前端建议 Vue3 + Vite + TypeScript + Element Plus；教学快速演示可先 Gradio，但最终交付以 Vue3 为目标。
- Pytest + httpx + Ruff；Docker Compose；GitHub Actions（可选）。
- 依赖版本按实施当日稳定兼容版本锁定，先验证 LangGraph、MCP SDK、模型 SDK 组合，禁止未经测试的自动大版本升级。

## 2. 模块划分

`frontend -> FastAPI -> {auth, procurement, knowledge, agent, approvals, audit}`

`agent -> harness.run -> LangGraph graph -> {LLM adapter, RAG retriever, Tool Registry, MCP Client}`

`RAG -> text extraction -> chunk -> embedding adapter -> Chroma`

`Tool Registry -> local DB tools | MCP tools`；所有工具调用经过参数验证、授权、审计。

**职责边界**：
- LLM：语言理解、草稿提取、建议撰写、选择允许的只读工具。
- RAG：检索企业制度，返回来源和置信信息；不直接写业务数据库。
- Tool Calling：模型通过声明的工具 schema 请求工具；后端校验并执行。
- MCP：为库存、供应商等工具提供标准化暴露与消费方式；不绕过权限层。
- LangGraph：保存状态、条件分支、人工审批暂停/恢复。
- Agent Workflow：围绕采购业务的确定性步骤和必要的模型节点。
- Agent Harness：统一执行入口、权限、限制、日志、重试、超时与恢复约束；它是一组工程能力，不是必须安装的单一框架。

## 3. 推荐目录

```text
enterprise-ai-agent-hub/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/{auth,chat,procurements,approvals,knowledge,inventory,suppliers,runs}.py
│   │   ├── core/{config,security,permissions,errors,logging}.py
│   │   ├── db/{base,session,models,seed}.py
│   │   ├── schemas/
│   │   ├── services/{procurement,approval,inventory,supplier}.py
│   │   ├── llm/{base,mock,openai_compatible}.py
│   │   ├── rag/{loader,chunker,embedding,retriever,indexer}.py
│   │   ├── agent/{graph,state,nodes,tools}.py
│   │   ├── harness/{runner,policy,limits,trace}.py
│   │   └── mcp/{server,client,registry}.py
│   ├── alembic/
│   ├── tests/{unit,integration,e2e}/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
├── sample_data/{policies,seed}/
├── docs/
├── .env.example
├── compose.yaml
└── README.md
```

## 4. 数据模型（建议表）

统一使用 UUID 主键（或显式采用 bigint，项目中只能选择一种）。时间戳均为 UTC，展示时本地化。金额 `NUMERIC(14,2)`，Python 使用 `Decimal`。

| 表 | 核心字段 | 约束 |
|---|---|---|
| users | id, username, password_hash, role, department_id, is_active, created_at | username 唯一 |
| departments | id, name | name 唯一 |
| inventory_items | id, sku, category, model, available_qty, unit_price, updated_at | sku 唯一，库存非负 |
| suppliers | id, name, is_active, created_at | name 非空 |
| supplier_quotes | id, supplier_id, inventory_item_id, unit_price, currency, quoted_at | price > 0 |
| purchase_requests | id, requester_id, title, category, quantity, unit_price_limit, total_budget, status, version, created_at, updated_at | quantity > 0；status 枚举 |
| purchase_candidates | id, request_id, item_id, supplier_id, quantity, unit_price, total_price | total_price 由服务端计算 |
| approval_rules | id, threshold_min, threshold_max, stage, approver_role, is_active | 区间与阶段须合法 |
| approval_tasks | id, request_id, stage, assignee_id, status, decision_comment, decided_at | 同一阶段同一审批任务防重复 |
| knowledge_documents | id, filename, sha256, storage_path, status, uploaded_by, created_at | hash 防重复活跃索引 |
| knowledge_chunks | id, document_id, chunk_index, content, page_number, vector_id | document_id+chunk_index 唯一 |
| agent_runs | id, user_id, request_id, status, started_at, finished_at, error_code, graph_thread_id | run_id 唯一 |
| agent_steps | id, run_id, step_index, node_name, tool_name, duration_ms, status, input_summary, output_summary, error_code | 可排序 |
| audit_events | id, actor_id, resource_type, resource_id, action, old_value, new_value, created_at | 不可静默修改 |

建议在 `purchase_requests` 中另存结构化 `requirements_json`（用途、优先级等），数据库层校验基本结构，应用层做完整 schema 校验。

## 5. REST API 规范

统一前缀 `/api/v1`，成功响应直接返回资源对象；错误格式：

```json
{"error":{"code":"FORBIDDEN","message":"无权操作此资源","request_id":"..."}}
```

| Method | Path | 用途/权限 |
|---|---|---|
| POST | /auth/login | 登录，返回 JWT |
| GET | /auth/me | 当前用户 |
| POST | /chat/parse-intent | 提取采购草稿（需登录） |
| POST | /chat/runs | 启动 Agent run，返回 run_id |
| GET | /runs/{run_id} | 查看本人或管理员的运行状态 |
| GET | /runs/{run_id}/steps | 运行步骤 |
| POST | /procurements | 创建草稿 |
| GET | /procurements | 按权限分页查询 |
| GET | /procurements/{id} | 查看详情 |
| PATCH | /procurements/{id} | 仅修改本人 DRAFT |
| POST | /procurements/{id}/plan | 生成采购方案 |
| POST | /procurements/{id}/submit | 提交审批，幂等 |
| GET | /approvals/inbox | 待审批任务 |
| POST | /approvals/{task_id}/decision | APPROVE/REJECT，幂等键 |
| GET | /inventory | 库存查询 |
| GET | /suppliers/quotes | 供应商报价查询 |
| POST | /knowledge/documents | ADMIN 上传文件 |
| GET | /knowledge/documents | ADMIN 列表 |
| DELETE | /knowledge/documents/{id} | ADMIN 删除文档及向量 |
| POST | /knowledge/search | 权限范围内检索，带引用 |
| GET | /healthz | 存活检查 |
| GET | /readyz | 依赖就绪检查 |

分页参数：`page>=1`、`page_size=1..100`；列表响应 `{items,total,page,page_size}`。所有写接口必须验证身份；敏感写接口接受 `Idempotency-Key`。

## 6. LLM / Embedding 适配器

```python
class LLMProvider(Protocol):
    async def extract_purchase_intent(self, text: str) -> PurchaseIntent: ...
    async def answer_with_context(self, question: str, contexts: list[str]) -> str: ...
    async def choose_tool(self, request: str, available_tools: list[dict]) -> ToolChoice | None: ...

class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

- `MODEL_PROVIDER=mock|openai_compatible`，`EMBEDDING_PROVIDER=mock|remote`。
- Mock 必须对种子演示输入给出**可复现**输出；不能用随机向量配合向量搜索假装语义检索。Mock 检索可使用确定性关键词/TF-IDF 路径，明确标记 Mock；真实模式才验证 Embedding + Chroma。
- 真实 Embedding 模型改变维度时应重建对应 collection，不可混用。
- 模型返回结果必须 schema 校验；最多一次修复性重试，失败返回结构化错误。
- 不得把密钥、完整用户身份信息发送给模型。

## 7. RAG 设计

文档上传 -> MIME/扩展名/大小校验（默认 <= 10MB）-> 提取 -> 清洗 -> 按 500-800 字符切块、重叠 80-120 字符 -> 生成向量 -> 存 Chroma -> 存 chunk 元数据。

检索默认 top_k=5；按文档可见性过滤；回答附 `document_id, filename, page_number, chunk_id, excerpt`。对空结果或低相关度做拒答。PDF 扫描件 OCR 为扩展功能，MVP 先支持文本型 PDF。

## 8. LangGraph 工作流定义

```text
START
  -> parse_intent
  -> validate_intent
  -> retrieve_policy
  -> query_inventory_and_quotes
  -> build_plan
  -> deterministic_budget_check
  -> human_confirm_plan [interrupt]
  -> persist_and_submit
  -> resolve_approval_chain
  -> await_approval [interrupt]
     ├─ REJECT -> record_rejection -> END
     └─ APPROVE -> next_approval_or_finalize -> END
```

- `thread_id` 与业务 request_id 关联，checkpoint 使用持久化存储（PostgreSQL 或官方支持的持久化 saver），不能只用进程内 MemorySaver 作为交付版。
- Graph state 建议包含 `run_id, request_id, user_id, intent, policy_sources, inventory_results, quotes, plan, approval_stage, errors`。
- 只有经过 API 权限验证的审批动作才能恢复 `await_approval`；恢复时再次校验状态、版本号和操作者。
- **注意**：若业务先由用户手工确认草稿并创建 request，则 `human_confirm_plan` 可由 API 外部确认实现，不必在图中重复暂停；实现时选定一种路径并保持一致。

## 9. Tool Calling 与 MCP

至少提供 3 个只读工具：

```json
{"name":"inventory.search","input":{"category":"laptop","min_qty":10},"output":{"items":[]}}
{"name":"supplier.quote","input":{"item_id":"uuid","quantity":10},"output":{"quotes":[]}}
{"name":"policy.search","input":{"query":"笔记本审批额度"},"output":{"citations":[]}}
```

- 本地 Tool Registry 实现输入 schema、输出 schema、调用权限、超时和审计。
- MCP Server 暴露 `inventory_search`、`supplier_quote`（至少两个工具），Client 能发现并调用；Agent 通过统一工具接口使用 MCP。
- MCP 工具名称与内部业务服务映射明确；**禁止**绕过业务服务直接执行任意 SQL、shell、文件系统写操作。
- MCP Server 的访问必须受控，演示环境优先本地 stdio；如改 HTTP 必须补充鉴权与网络边界。

## 10. Mini Agent Harness

定义统一 `AgentRunner.run(user, input, allowed_tools, context)`：
1. 生成 run_id、保存执行元数据。
2. 基于用户角色与当前状态构建允许的工具白名单。
3. 限制最大步数（8）、最大总时长（60s）、单工具超时（5s）。
4. 记录每次工具调用的耗时、结果、错误和摘要。
5. 对只读、幂等工具执行有限重试；写操作默认不自动重试。
6. 任务异常时写入失败状态，不吞异常；支持查询运行结果。
7. 防提示词注入：外部文档、工具返回均视为数据，不视为系统指令。
8. 高风险动作（审批、下单、支付、删除）不可交给自主 Agent 自动执行。

## 11. 审批业务与事务安全

- 审批链由 `approval_rules` 生成，金额来自数据库中的候选明细总和。
- `approval_tasks` 决策使用事务、乐观锁版本号、幂等键。
- 审批人必须与当前 task assignee 匹配；禁止自审。
- 同一 task 的重复相同决策可返回既有结果；冲突决策返回 409。
- 写入审批决定与业务状态时需考虑 graph checkpoint 的最终一致性：先持久化业务事件，再可靠恢复图；恢复失败允许安全重放且不重复审批。

## 12. 安全与可观测性

- JWT access token；密码 Argon2/bcrypt；角色鉴权；上传文件大小/类型检查；SQLAlchemy 参数化查询。
- 环境变量管理密钥；日志脱敏；不把完整文档或用户敏感数据写入 traces。
- 每个 API request_id、agent run_id、graph thread_id 关联追踪。
- 结构化日志 JSON；API 错误码稳定；前端提示友好。
- 最低测试：鉴权、权限越权、自审、金额计算、审批状态机、幂等、Mock RAG、MCP 调用、Harness 超时/步数上限。


## V1.1 实施优先级与契约
如本文件的示意接口、表结构与专项规范不一致，以 `API_SPEC.md`、`DATABASE_DESIGN.md`、`AGENT_WORKFLOW.md` 为准；涉及安全业务不变量以 PRD 为准。用户角色支持多角色与 TECH_ADMIN；知识库 ACL 和 SSE 事件必须按专项文档实现。前端只参考用户截图的视觉语言，不复制截图中的业务内容。
