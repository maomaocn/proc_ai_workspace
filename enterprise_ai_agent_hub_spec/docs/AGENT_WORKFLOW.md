# Agent Workflow、LangGraph、MCP 与 Harness 设计 V1.1

## 1. 技术职责与调用关系

当前实现不是一条所有组件都顺序经过的单链，而是由 FastAPI 暴露的三条受控链路：

1. `FastAPI -> LLM Adapter -> Pydantic -> 人工确认 -> 采购草稿`。
2. `FastAPI -> 采购服务 -> Tool Registry -> {RAG, DB Tool}`。
3. `FastAPI -> 审批服务 -> LangGraph interrupt/checkpoint/resume`。
4. 技术测试链路为 `FastAPI -> AgentRunner(Harness) -> Tool Registry -> MCP Client -> MCP Server`。

Harness 是受限工具执行器，不是独立大模型或自主 Planner。LangGraph 是审批状态机和持久化
恢复框架。详细源码导读见 `AI_AGENT_PIPELINE_GUIDE.md`。

## 2. 采购执行流程
1. `parse_intent`：LLM 对当前消息提取需求，Pydantic 校验；缺字段返回追问。
2. `confirm_intent`：用户核对结构化卡片后创建采购草稿；这一步不经过 LangGraph。
3. `build_plan`：采购服务以固定顺序调用库存、制度 RAG、供应商报价工具。
4. `compose_proposal`：服务端使用 Decimal 计算并保存候选；当前不调用 LLM 生成方案。
5. `validate_rules`：读取数据库审批规则，按派生总额计算审批链。
6. `submit_for_approval`：用户显式提交，事务创建审批任务和审计，再启动 LangGraph。
7. `await_approval`：LangGraph `interrupt` 将状态写入 PostgreSQL checkpoint 后暂停。
8. `human_approval`：受保护 API 验证审批人、自审、顺序、幂等后写业务决定。
9. `resume`：持久化恢复事件驱动 `Command(resume=...)`，进入下一阶段或终点。
10. `finalize`：全部批准后为 APPROVED；采购履约由 PROCUREMENT 独立操作。

**关键约束**：LLM 只负责理解、总结、建议和选择被授权的只读工具；任何采购状态、金额、审批规则和权限均由后端代码决定。前端节点图反映真实运行，不用于修改业务规则。

## 3. 当前 GraphState 字段

`run_id, purchase_request_id, requester_id, total_budget, approval_stages[], current_stage_index,
current_stage, pending_human_action, last_decision, status, errors[], step_count`。状态全部可序列化，
不存明文密钥。checkpoint 只保存工作流位置，权限仍由业务 API 和 PostgreSQL 业务表验证。

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
- 统一 `AgentRunner.run()`：角色/策略权限、执行循环、允许工具列表、最大步骤、单工具超时、总执行超时、只读有限重试、追踪和错误处理。
- 每次执行生成 run_id；每步记录 seq、node/tool、状态、开始/结束、耗时、脱敏摘要、错误码；敏感数据和 API Key 不记录。
- 当前 Harness 接收已经规划好的 `AgentCall` 列表，不自主调用 LLM 规划；运行状态持久化为 `AgentRun/AgentStep/AgentEvent`。
- 限额触发应有 `STEP_LIMIT_EXCEEDED`、`TOOL_TIMEOUT`、`TOOL_NOT_ALLOWED` 等可解释错误，UI 展示恢复建议。

## 7. Mock 与真实模式
Mock LLM 使用确定性规则和固定种子数据，Embedding/检索可用稳定伪实现；真实模式通过 Provider Adapter 调用兼容 API。两种模式的业务 API 结构相同；Mock 返回必须标注 `source: MOCK` 或 demo 数据标记。模型不可用时不得伪装真实结果。

## 8. 工作流验收
至少覆盖：完整采购、缺字段追问、无制度证据、工具超时、非法工具、自审拒绝、重复审批、多级审批、审批中断恢复、SSE 断线重连、超步数终止、Mock 可复现。
