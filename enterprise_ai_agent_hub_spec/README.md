# Enterprise AI Agent Hub — V1.1 完整需求基线

**状态：待产品负责人评审，尚未授权实施；适用：Codex CLI；语言：中文。**

目标：在企业采购与办公协同场景中，将 LLM、Embedding、RAG、Agent、Tool Calling、LangGraph、Agent Workflow、MCP、Mini Agent Harness 串成可追溯的真实业务闭环。采购、报价和库存均使用演示数据；不连接真实付款、外部采购或生产 ERP。

## 如何阅读

1. `docs/PRD.md`：产品目标、用户故事、权限、状态与业务不变量。
2. `docs/FRONTEND_PRD.md`：完整页面清单、字段、操作、角色、状态、异常与路由。
3. `docs/UI_DESIGN_SPEC.md`：仅借鉴用户参考截图的**视觉风格**，不复制截图中的业务、内容或布局。
4. `docs/ARCHITECTURE.md`：总体技术方案；`docs/DATABASE_DESIGN.md`：实体和数据库约束。
5. `docs/API_SPEC.md`：HTTP 接口契约、分页、错误、SSE；`docs/AGENT_WORKFLOW.md`：编排与恢复。
6. `docs/ACCEPTANCE_CRITERIA.md`：功能与安全验收矩阵。
7. `docs/IMPLEMENTATION_PLAN.md` 与 `docs/phases/M0.md`～`M6.md`：Codex 阶段开发任务。
8. 根目录 `AGENTS.md`：Codex 自动识别“开始 M1 阶段任务”等命令。
9. `docs/AI_AGENT_PIPELINE_GUIDE.md`：按真实源码调用链理解 LLM、RAG、Workflow、Harness、MCP 与 Memory。

## 文档优先级
安全和业务不变量 > PRD > API/数据库/工作流专项规范 > 前端 PRD/UI > 架构建议 > 阶段计划。冲突须报告，不得静默自行改变业务规则。

## 使用方法
将本需求包文件放到项目根目录。Codex 在项目根目录启动后输入 `开始 M0 阶段任务`，后续输入 `开始 M1 阶段任务` 等。阶段自动化仅在 Codex 能读取本地仓库且具备必要执行权限时生效。**本包只包含需求、规范、种子示例，不包含已实现的系统代码。**

## 范围说明
- P0：认证、AI 对话/意图、知识库、采购申请、审批闭环、基本追踪。
- P1：Workflow 节点可视化、MCP 工具测试、Harness 诊断与控制。
- P2：高级报表、个性化与非核心增强，不阻塞 V1.0 核心交付。
- 教学：可先 Mock，再切换真实模型；不以 Dify/Coze 作为核心运行依赖。
