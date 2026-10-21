# API 接口契约 V1.1

## 1. 通用规则
前缀 `/api/v1`；JSON UTF-8；JWT Bearer；所有资源必须服务端鉴权及行级授权。分页 `page>=1&page_size=1..100`，返回 `{"items":[],"page":1,"page_size":20,"total":0}`。成功返回资源 JSON；错误统一 `{"error":{"code":"FORBIDDEN","message":"无权操作此资源","request_id":"uuid","details":{}}}`。时间 ISO8601 UTC；金额以**字符串**传输（如 `"6000.00"`），禁止 JS 浮点计算。写操作携带 `Idempotency-Key`（特别是提交、审批、状态变更）；服务端校验。`GET` 可安全重试，写操作不得盲目重试。

## 2. 核心接口矩阵
| Method | Endpoint | 权限 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | 公共 | 用户名密码换 JWT |
| GET | `/auth/me` | 登录 | 当前用户及 roles |
| GET/POST | `/chat/sessions` | 登录 | 会话列表/新建 |
| GET/PATCH | `/chat/sessions/{id}` | 会话所有者 | 详情/改名/归档 |
| GET | `/chat/sessions/{id}/messages` | 会话所有者 | 消息分页 |
| POST | `/chat/parse-intent` | 登录 | 结构化意图提取；无需提交采购 |
| POST | `/chat/sessions/{id}/messages` | 会话所有者 | 发送消息，返回 run_id 与流地址 |
| GET | `/agent-runs/{run_id}/events` | 运行所有者/技术角色 | SSE 事件流 |
| GET | `/agent-runs/{run_id}` | 运行所有者/技术角色 | 运行摘要；普通员工字段脱敏 |
| GET/POST | `/knowledge/collections` | 授权库/ADMIN | 库列表/创建库及角色只读 ACL |
| GET/POST | `/knowledge/documents` | 库读/写权限 | 文档列表/上传 multipart |
| GET/DELETE | `/knowledge/documents/{id}` | 库权限 | 文档详情/删除 |
| POST | `/knowledge/documents/{id}/reindex` | 管理员 | 重建索引 |
| POST | `/knowledge/search` | 库读权限 | 检索与引用 |
| GET/POST | `/procurements` | 登录 | 列表/创建草稿 |
| GET/PATCH | `/procurements/{id}` | 资源权限 | 详情/编辑草稿 |
| POST | `/procurements/{id}/plan` | 申请人草稿 | 只读工具生成候选方案与制度依据 |
| POST | `/procurements/{id}/submit` | 申请人 | 提交审批 |
| POST | `/procurements/{id}/cancel` | 申请人 | 仅草稿取消 |
| GET | `/approvals/tasks` | APPROVER | 我的待办/历史 |
| GET | `/approvals/tasks/{id}` | 指派审批人 | 审批详情 |
| POST | `/approvals/tasks/{id}/decision` | 指派审批人 | 批准/驳回 |
| GET | `/inventory/items` | 登录 | 库存查询 |
| POST/PATCH | `/inventory/items[/{id}]` | ADMIN | 库存维护 |
| GET/POST | `/suppliers` | PROCUREMENT/ADMIN | 供应商列表/新增 |
| GET/POST | `/supplier-quotes` | PROCUREMENT/ADMIN | 报价列表/新增 |
| POST | `/procurements/{id}/fulfillment-transition` | PROCUREMENT | ORDERED/RECEIVED/CLOSED |
| GET | `/workflows/runs/{run_id}` | TECH_ADMIN/ADMIN | 节点执行图及状态 |
| GET | `/agent-runs` | TECH_ADMIN/ADMIN | Harness 运行列表 |
| GET | `/agent-runs/{run_id}/steps` | TECH_ADMIN/ADMIN | 脱敏步骤 |
| GET | `/mcp/servers` | TECH_ADMIN/ADMIN | 服务列表及健康 |
| GET | `/mcp/tools` | TECH_ADMIN/ADMIN | 工具 schema/权限 |
| POST | `/mcp/tools/{tool_id}/test` | TECH_ADMIN/ADMIN | 仅白名单只读工具 |
| GET/POST | `/admin/users` | ADMIN | 用户列表/创建 |
| GET/POST | `/admin/approval-rules` | ADMIN | 审批规则列表/创建 |

## 3. 关键请求响应示例
> M3 已实现采购草稿、方案、库存、供应商和报价接口。提交、取消、审批、履约、工作流、
> MCP 与 Harness 接口仍是后续阶段契约，本阶段不得视为可调用接口。

**意图解析** `POST /chat/parse-intent`：
```json
{"text":"采购10台笔记本，每台预算6000元以内","session_id":null}
```
响应（未填写字段用 null；`missing_fields` 用于追问）：
```json
{"intent":{"category":"笔记本电脑","item_description":"笔记本电脑","quantity":10,"unit_price_limit":"6000.00","total_budget":"60000.00","purpose":null,"priority":"NORMAL","notes":null},"missing_fields":["purpose"],"requires_confirmation":true,"source":"MOCK"}
```
**创建采购草稿** `POST /procurements`：
```json
{"title":"研发设备采购","category":"笔记本电脑","item_description":"办公笔记本","quantity":10,"unit_price_limit":"6000.00","total_budget":"60000.00","purpose":"研发办公","priority":"NORMAL","notes":""}
```
响应包含 `id`、`status:"DRAFT"`、`version:0`、`created_at`。

**生成采购方案** `POST /procurements/{id}/plan`：仅申请人自己的 `DRAFT` 可执行。
服务端依次调用 `inventory.search`、`policy.search` 和匹配商品的 `supplier.quote`，返回
`procurement.candidates`、`policy` 与只读 `tool_calls` 摘要。报价来源固定标识为 `DEMO`；
金额以两位小数字符串传输并由服务端 `Decimal` 计算。

**审批决策** `POST /approvals/tasks/{id}/decision`：Header `Idempotency-Key: <uuid>`；Body `{"action":"REJECT","comment":"预算依据不足"}`。`APPROVE` 可附评论，`REJECT` 必填 5~500 字。返回 `task_id`、`task_status`、`purchase_status`、`decision_id`、`workflow_run_id`。
**检索** `POST /knowledge/search`：`{"collection_id":"uuid","query":"笔记本审批要求","top_k":5}`；返回 `{"hits":[{"document_id":"uuid","filename":"采购制度.pdf","chunk_id":"uuid","page_number":2,"snippet":"...","score":0.82}],"answer":"根据《采购制度.pdf》第 2 页：...","source":"MOCK","has_sufficient_evidence":true}`。无命中时 `hits=[]`、`has_sufficient_evidence=false`，并明确回答“当前知识库未检索到足够依据”。score 仅为实际检索器返回的分数，不强制不同引擎间可比。

**文档上传** `POST /knowledge/documents` 使用 multipart 字段 `collection_id` 与 `file`；仅支持 PDF/TXT/MD，单文件默认最大 20MB。相同 collection 中同 SHA-256 的非删除文档返回 409；索引失败保留 FAILED 状态与稳定 `error_code`。

## 4. SSE 事件契约
`GET /agent-runs/{run_id}/events`，`Content-Type: text/event-stream`；支持 `Last-Event-ID` 恢复已持久化事件，或重新 GET run 状态；事件至少包含 `id`、`event`、`data`。事件类型：`run.started`、`message.delta`、`node.started`、`node.completed`、`tool.started`、`tool.completed`、`run.waiting_approval`、`run.completed`、`run.failed`、`heartbeat`。`data` 通用字段 `run_id`、`seq`、`timestamp`，按事件扩展 `node`、`text_delta`、`tool_name`、`status`、`error_code`、`request_id`。前端按 seq 去重排序；断线重连只订阅，不重新发起写请求。敏感参数不进入事件。

## 5. HTTP 状态与错误码
400 `VALIDATION_ERROR`；401 `UNAUTHORIZED`；403 `FORBIDDEN`；404 `NOT_FOUND`；409 `STATE_CONFLICT`/`IDEMPOTENCY_CONFLICT`；413 `FILE_TOO_LARGE`；415 `UNSUPPORTED_MEDIA_TYPE`；422 `BUSINESS_RULE_VIOLATION`；429 `RATE_LIMITED`；503 `MODEL_UNAVAILABLE`/`TOOL_UNAVAILABLE`。所有错误带 request_id；对外不返回堆栈和密钥。

## 6. API 实现约定
接口表是 V1.1 开发基线；OpenAPI 由 FastAPI 生成并与前端 TS DTO 保持一致；任何改动同步更新本文件、自动化契约测试与对应阶段任务。技术页面禁止任意执行 MCP 写工具。
