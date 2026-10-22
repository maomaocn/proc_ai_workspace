# 数据库设计 V1.1（PostgreSQL 16）

## 1. 统一约束
所有主键 UUID；时间 `timestamptz` 存 UTC；金额 `numeric(14,2)`，币种 MVP 仅 CNY；数量整数；业务状态用 CHECK 或受控 enum；`created_at`、`updated_at` 默认审计。外键与索引必须经 Alembic 迁移。数据库连接使用独立最小权限账户；禁止生产自动建表。

## 2. 核心实体与约束
| 表 | 必需字段（除 id、时间） | 关键约束/索引 |
|---|---|---|
| departments | name | name UNIQUE |
| users | username, password_hash, department_id, is_active | username UNIQUE；password_hash 非明文 |
| user_roles | user_id, role | (user_id, role) UNIQUE；role 属于 EMPLOYEE/APPROVER/PROCUREMENT/ADMIN/TECH_ADMIN |
| chat_sessions | owner_id, title, archived_at | (owner_id, updated_at) 索引 |
| chat_messages | session_id, sender, content, status, run_id | (session_id, created_at) 索引；content 限长 |
| knowledge_collections | name, visibility, created_by | collection 名称非空；按库 ACL 授权 |
| knowledge_acl | collection_id, principal_type, principal_id, permission | 唯一授权键 |
| knowledge_documents | collection_id, filename, sha256, mime_type, size_bytes, storage_path, status, uploaded_by, index_version, error_code | 同库活跃 sha256 唯一；size_bytes>0；状态 PENDING/INDEXING/READY/FAILED/DELETED |
| knowledge_chunks | document_id, chunk_index, content, page_number, vector_id | (document_id,chunk_index) UNIQUE；向量删除同步 |
| inventory_items | sku, category, model, available_qty, reference_price, active | sku UNIQUE；available_qty>=0 |
| suppliers | name, active, demo_data | name 非空 |
| supplier_quotes | supplier_id, inventory_item_id, unit_price, currency, quoted_at, source_type | unit_price>0；来源明确 DEMO |
| purchase_requests | requester_id, title, category, item_description, quantity, unit_price_limit, total_budget, purpose, priority, notes, status, version, linked_run_id | quantity>0；金额>0；version>=0；(requester_id,created_at) 索引 |
| purchase_candidates | request_id, item_id, supplier_id, quantity, unit_price, total_price, source_quote_id | total_price 服务端 Decimal 计算 |
| approval_rules | min_amount, max_amount, stage, approver_role, active | min>=0；max>min 或 NULL；禁止有效规则冲突/缺口 |
| approval_tasks | request_id, stage, assignee_id, status, decision_comment, decided_at | (request_id,stage,assignee_id) UNIQUE；待办索引 |
| approval_decisions | task_id, actor_id, action, comment, idempotency_key, created_at | (actor_id,idempotency_key) UNIQUE；不可变更 |
| agent_runs | user_id, request_id?, graph_thread_id?, run_type, status, started_at, finished_at, error_code, model_provider, max_steps, total_timeout_ms, step_count, tool_call_count, retry_count | graph_thread_id UNIQUE（非空时）；状态索引；限额大于 0 |
| agent_steps | run_id, step_index, node_name, tool_name, status, duration_ms, input_summary, output_summary, error_code, started_at, finished_at | (run_id,step_index) UNIQUE；敏感字段脱敏 |
| agent_events | run_id, seq, event_type, data_json, created_at | (run_id,seq) UNIQUE；只存脱敏事件 |
| mcp_servers | name, transport, config_ref, enabled, health_status | 不存明文凭据 |
| tool_policies | tool_name, allowed_roles, read_only, enabled, max_calls_per_run | 拒绝优先；最小权限 |
| audit_events | actor_id, action, resource_type, resource_id, before_json, after_json, request_id, created_at | 只追加，不允许业务接口修改 |

## 3. 业务关系
部门 1:N 用户；用户 N:M 角色；用户 1:N 会话、采购单；会话 1:N 消息；知识库 1:N 文档 1:N 分块；采购单 1:N 候选方案与审批任务；运行 1:N 步骤；采购单与 run 可关联但不强制一一对应。

## 4. 状态机与事务
采购：`DRAFT→SUBMITTED→PENDING_APPROVAL→APPROVED→ORDERED→RECEIVED→CLOSED`；`PENDING_APPROVAL→REJECTED`；`DRAFT→CANCELLED`。SUBMITTED 为短暂内部状态，提交 API 返回 PENDING_APPROVAL 或明确错误。审批任务：PENDING→APPROVED/REJECTED，禁止反向变更。
- 申请提交、审批决策、状态变更均在数据库事务中完成；使用版本号 compare-and-swap 或 `SELECT ... FOR UPDATE`；记录审计事件。
- 多级审批按 stage 升序创建/激活任务；任何阶段拒绝则整单 REJECTED；全部批准才 APPROVED。
- 审批幂等键必须持久化并对 actor 作用域唯一；同键同请求返回原结果，同键不同请求返回 409。
- MCP 和 LLM 不能直接更新审批任务或采购状态。

## 5. 删除与保留
知识库删除使用 DELETED 状态，后台同步移除向量并清理文件；删除失败进入可重试队列，检索立即过滤 DELETED；业务审计不级联删除。演示数据可通过专用 seed 命令创建，不得在生产自动重置。
