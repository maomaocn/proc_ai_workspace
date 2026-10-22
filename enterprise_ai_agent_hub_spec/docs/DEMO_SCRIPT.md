# M6 全链路演示脚本

## 演示前检查（约 2 分钟）

1. 执行 `docker compose ps`，确认 db、api、frontend 均为 healthy。
2. 打开 `http://localhost:8000/healthz`，确认版本为 `0.7.0`。
3. 确认 `MODEL_PROVIDER=mock`、`EMBEDDING_PROVIDER=mock`，不配置真实 Key。

## 主链路（约 12 分钟）

1. `employee` 登录 AI 采购助手，输入“采购10台笔记本，每台6000元”。确认系统追问用途。
2. 填写“研发办公”并确认草稿。打开采购详情，确认数量 10、单价 6000.00、总预算
   60000.00。
3. 生成候选方案，指出库存和报价来自 PostgreSQL DEMO 数据，金额由服务端 Decimal 计算。
4. 在知识库检索“笔记本超过一万元需要几级审批”，展示真实文档引用或明确无依据回复。
5. 提交采购申请，确认审批链为 `manager → approver`，状态为 `PENDING_APPROVAL`。
6. `manager` 登录并批准第一级，状态仍为审批中；`approver` 登录批准第二级，状态变为
   `APPROVED`。
7. `procurement` 登录“采购申请与履约”，打开该申请，依次执行模拟下单、模拟收货和关闭。
   每一步确认版本递增、状态不可跳跃、审计时间线增加一条记录。
8. 切回 `employee`，确认申请状态为 `CLOSED`。

## 技术链路（约 5 分钟）

1. `techadmin` 打开 MCP 工具中心，发现两个 stdio 只读工具并执行库存查询。
2. 打开生成的 Harness run，展示调用次数、重试、耗时、脱敏摘要与 SSE 事件。
3. 打开 Workflow 运行详情，展示真实审批节点、暂停和恢复路径。
4. 说明 `techadmin` 不能审批或执行履约，`admin` 也不能跳过业务角色推进履约。

## 失败分支（约 3 分钟）

- 未批准申请尝试 `ORDERED`：返回 409 `STATE_CONFLICT`。
- 从 `APPROVED` 直接跳到 `RECEIVED`：返回允许的下一状态 `ORDERED`。
- 相同幂等键与相同负载：返回原结果；相同键不同负载：返回
  `IDEMPOTENCY_CONFLICT`。
- 无权限用户调用履约接口：返回 403；未登录访问保护接口：返回 401。

所有账号的本地演示密码均为 `DemoPass123!`，仅限本地 seed 环境。

