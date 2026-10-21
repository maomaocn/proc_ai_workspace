# Agent Workflow、LangGraph、MCP 与 Harness 设计 V1.1

## 1. 技术职责与调用关系
`FastAPI → AgentRunner(Harness) → LangGraph Workflow → {LLM Adapter, RAG, Tool Registry} → {DB Tool, MCP Client→MCP Server}`。Harness 是执行管理能力组合，不是独立大模型或必须引入的第三方产品。LangGraph 是实现状态与条件流转的框架，Agent Workflow 是业务编排模式。

## 2. 采购执行流程
1. `parse_intent`：LLM 提取需求，Pydantic 校验；缺字段返回追问，不做写操作。
2. `retrieve_policy`：按用户知识库 ACL 做 RAG 检索；返回引用和是否有足够证据；无依据不能编造规则。
3. `query_inventory`：Tool Calling 选择允许的只读库存工具，验证 schema/权限。
4. `query_quotes`：查演示供应商报价（可经 MCP）；标注 DEMO 和报价时间。
5. `compose_proposal`：LLM 解释方案，价格和预算由 Decimal 确定性计算。
6. `confirm_draft`：中断等待用户确认；未经确认不得创建采购草稿或提交。
7. `validate_rules`：读取数据库审批规则，按总金额计算审批链；规则缺失时停止并提示配置。
8. `submit_for_approval`：用户显式提交，服务端事务创建审批任务、写审计并暂停工作流。
9. `human_approval`：通过受保护 API 批准/驳回，禁止自审；多级按顺序激活。
10. `finalize`：全部批准后更新 APPROVED，后续采购履约由 PROCUREMENT 独立操作。

**关键约束**：LLM 只负责理解、总结、建议和选择被授权的只读工具；任何采购状态、金额、审批规则和权限均由后端代码决定。前端节点图反映真实运行，不用于修改业务规则。

## 3. GraphState 建议字段
`run_id, thread_id, user_id, session_id, purchase_request_id?, user_input, intent?, missing_fields[], policy_citations[], inventory_hits[], supplier_quotes[], proposal?, rule_validation?, approval_stage?, approval_task_id?, pending_human_action?, status, errors[], step_count`。状态可序列化，不在 checkpoint 存明文密钥；checkpoint 绑定用户与会话权限。

## 4. 中断/恢复/幂等
- 需要人工确认的节点通过 LangGraph interrupt/checkpoint 暂停；持久化 checkpoint 使用 PostgreSQL 兼容存储或经验证的适配器；不得仅使用内存存储作为正式交付。
- 恢复必须验证 actor、审批任务、资源权限、预期状态和版本号；恢复事件与审批数据库事务的边界需有可靠重放策略（outbox 或可幂等恢复）。
- 重放后不可重复提交采购、重复审批或重复扣减库存；MVP 不做库存扣减和真实下单。
- 写操作绝不自动重试；只读工具允许有限指数退避（默认最多 2 次），须考虑超时与总预算。

## 5. Tool Calling 与 MCP
- Tool Registry 每个工具声明 `name, description, input_schema, required_permissions, side_effect, timeout_ms, max_calls_per_run`。
- 最小工具集：`inventory.search`、`supplier.quote`、`policy.search`；前两个可同时支持本地 Tool 和 MCP 适配路径以用于教学对照。
- MCP Server 默认本地 stdio 传输，Client 连接时检查服务端身份/配置；不信任工具返回中的指令文本；工具输入做类型/范围校验，结果限制大小。
- MCP 工具管理页面仅提供只读白名单测试；无任意 shell/SQL/文件系统写入工具。

## 6. Mini Agent Harness
- 统一 `AgentRunner.run()`：身份/资源权限、执行循环、允许工具列表、最大步骤（建议 12）、单工具超时（建议 10s）、总执行超时（建议 90s，等待人工审批时间不计入）、只读有限重试、取消信号、追踪和错误处理。
- 每次执行生成 run_id；每步记录 seq、node/tool、状态、开始/结束、耗时、脱敏摘要、错误码；敏感数据和 API Key 不记录。
- 状态：CREATED/RUNNING/WAITING_USER/WAITING_APPROVAL/SUCCEEDED/FAILED/CANCELLED；用户点击“停止”仅取消可中断的生成/只读执行，不撤销已提交的业务写操作。
- 限额触发应有 `STEP_LIMIT_EXCEEDED`、`TOOL_TIMEOUT`、`TOOL_NOT_ALLOWED` 等可解释错误，UI 展示恢复建议。

## 7. Mock 与真实模式
Mock LLM 使用确定性规则和固定种子数据，Embedding/检索可用稳定伪实现；真实模式通过 Provider Adapter 调用兼容 API。两种模式的业务 API 结构相同；Mock 返回必须标注 `source: MOCK` 或 demo 数据标记。模型不可用时不得伪装真实结果。

## 8. 工作流验收
至少覆盖：完整采购、缺字段追问、无制度证据、工具超时、非法工具、自审拒绝、重复审批、多级审批、审批中断恢复、SSE 断线重连、超步数终止、Mock 可复现。
