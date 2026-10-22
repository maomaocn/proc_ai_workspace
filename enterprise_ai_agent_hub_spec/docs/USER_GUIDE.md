# Enterprise AI Agent Hub 系统使用与权限手册

## 1. 使用范围

本系统用于本地教学、开发和验收。LLM、Embedding、库存、报价、下单、收货及关闭默认均为
Mock/DEMO，不会调用真实 ERP、供应商、支付或物流系统。

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`
- 存活检查：`http://localhost:8000/healthz`
- 就绪检查：`http://localhost:8000/readyz`

## 2. 演示账号

| 用户名 | 密码 | 部门 | 角色 |
|---|---|---|---|
| `employee` | `DemoPass123!` | 研发部 | EMPLOYEE |
| `manager` | `DemoPass123!` | 研发部 | EMPLOYEE、APPROVER |
| `approver` | `DemoPass123!` | 财务部 | EMPLOYEE、APPROVER |
| `procurement` | `DemoPass123!` | 采购部 | EMPLOYEE、PROCUREMENT |
| `admin` | `DemoPass123!` | 信息技术部 | EMPLOYEE、ADMIN |
| `techadmin` | `DemoPass123!` | 信息技术部 | TECH_ADMIN |

这些凭据仅用于本地 seed。生产环境必须关闭 `SEED_DEMO_DATA`、替换 JWT 密钥并使用正式
身份系统。`manager` 是演示用户名，不是独立角色。

## 3. 权限矩阵

| 功能 | EMPLOYEE | APPROVER | PROCUREMENT | ADMIN | TECH_ADMIN |
|---|---|---|---|---|---|
| AI 采购助手、本人会话 | 是 | 是 | 是 | 是 | 是 |
| 授权知识库检索 | 按 ACL | 按 ACL | 按 ACL | 管理 | 按 ACL，不自动授权 |
| 创建和编辑本人采购草稿 | 是 | 是 | 是 | 是 | 否，除非另授业务角色 |
| 查看库存 | 只读 | 只读 | 只读 | 维护 | 否，除非另授业务角色 |
| 审批采购申请 | 否 | 仅本人待办 | 否 | 否 | 否 |
| 供应商与 DEMO 报价 | 否 | 否 | 维护 | 维护 | 否 |
| 推进 ORDERED/RECEIVED/CLOSED | 否 | 否 | 是 | 否 | 否 |
| 审批规则 | 否 | 否 | 否 | 管理 | 否 |
| 用户管理 API | 否 | 否 | 否 | 是 | 否 |
| Workflow/MCP/Harness 观察 | 仅本人 run | 仅本人 run | 仅本人 run | 是 | 是 |
| MCP 工具测试 | 否 | 否 | 否 | 白名单只读 | 白名单只读 |

同一用户可以具备多个角色。前端隐藏菜单只改善体验，后端 RBAC、资源所有权和工具策略才是
最终权限依据。`ADMIN` 和 `TECH_ADMIN` 不会自动获得审批或履约写权限。

## 4. 员工操作

1. 使用 `employee` 登录，进入“AI 采购助手”。
2. 输入品类、数量、单价上限和用途；总额由数量乘以单价自动计算，当前版本不单独设置总预算；信息不足时根据追问补充。
3. 检查结构化草稿后点击“确认需求”。确认前不会创建采购申请。
4. 在“采购申请”中生成候选方案，查看 DEMO 库存、报价和制度引用。
5. 提交前确认审批链；提交后只能查看审批进度和审计时间线。
6. 最终审批通过后，员工只能查看采购履约状态，不能自行推进。

员工只能读取自己的会话和采购申请。知识库内容还会经过集合 ACL 校验。

## 5. 审批人操作

1. 使用 `manager` 或 `approver` 登录，进入“我的审批”。
2. 只可处理分配给自己的 `PENDING` 任务；后续级别在前一级通过前保持等待。
3. 批准可填写意见；驳回必须填写理由。
4. 申请人不能审批自己提交的采购申请。

演示金额规则默认不高于 10000 元走一级审批，高于 10000 元走两级顺序审批。

## 6. 采购人员操作

1. 使用 `procurement` 登录，在“供应商报价”维护本地 DEMO 数据。
2. 在“采购申请与履约”中查看已批准或履约中的申请。
3. 严格按 `APPROVED → ORDERED → RECEIVED → CLOSED` 推进。
4. 每次操作都需要显式确认，服务端要求最新版本和 UUID `Idempotency-Key`。

状态不可跳跃；同幂等键同负载返回原结果，同键不同负载返回 409。所有操作只更新本地状态。

## 7. 管理员和技术管理员

`admin` 可管理知识库、库存、供应商、用户 API 和审批规则，也可查看技术运行页面，但不能
审批或推进履约。用户管理当前通过 OpenAPI 的 `/api/v1/admin/users` 接口使用。

`techadmin` 可查看 Workflow、MCP 和 Harness 运行，检查节点、错误码、耗时、重试和脱敏
摘要，并试运行白名单内的只读 MCP 工具。技术权限不能绕过业务 RBAC。

## 8. 状态与审计

- 采购状态：`DRAFT → PENDING_APPROVAL → APPROVED/REJECTED`，批准后可进入履约状态。
- 履约状态：`APPROVED → ORDERED → RECEIVED → CLOSED`。
- 审批决定、提交、取消和履约状态变化写入 `audit_events`，包含操作者、前后状态和
  `request_id`。
- AI、Workflow 和 Harness 运行写入 `agent_runs`、`agent_steps`、`agent_events`。
- SSE 断线续传读取已有事件，不会重复执行采购或工具写操作。

## 9. 运行日志

API 应用日志为单行 JSON，核心字段如下：

| 字段 | 说明 |
|---|---|
| `timestamp` | UTC 时间 |
| `level` | INFO/WARNING/ERROR |
| `event` | `request.completed` 或 `request.failed` |
| `request_id` | 与响应头 `X-Request-ID`、业务审计关联 |
| `method`、`route` | HTTP 方法和路由模板，不含查询参数 |
| `status_code`、`duration_ms` | 响应状态和服务端耗时 |
| `actor_id`、`actor_roles` | 鉴权成功后记录 UUID 和角色，不记录用户名 |

日志不会记录 Authorization、Cookie、请求体、对话内容、文档正文或 API Key。查看方式：

```bash
docker compose logs --tail=200 api
docker compose logs -f api
```

容器关闭了会输出原始 URL 的 Uvicorn access log，以 JSON 应用日志作为 HTTP 请求日志。
JSON 应用日志、数据库审计和 Agent 轨迹用途不同，排障时可通过 `request_id`、资源 ID 或
`run_id` 关联。

## 10. 常见问题

- 401：登录缺失、token 无效或过期，重新登录。
- 403：当前角色或资源所有权不允许操作，不能通过直接输入 URL 绕过。
- 409：状态、版本或幂等键冲突，刷新详情后使用当前版本重试。
- 知识检索无结果：确认文档为 READY 且当前角色具有集合 ACL。
- 工具拒绝：检查工具白名单、数据库策略、只读属性和角色。
- 服务不可用：先检查 `/readyz` 和 `docker compose ps`，再查看 API 与数据库日志。

更详细的启动、备份和恢复操作见 `OPERATIONS_GUIDE.md`，演示流程见 `DEMO_SCRIPT.md`。
