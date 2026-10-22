import { createRouter, createWebHistory } from "vue-router"

import { auth } from "./auth/store"
import AppShell from "./components/AppShell.vue"
import ApprovalDetailView from "./views/ApprovalDetailView.vue"
import ApprovalRulesView from "./views/ApprovalRulesView.vue"
import ApprovalsView from "./views/ApprovalsView.vue"
import AssistantView from "./views/AssistantView.vue"
import DashboardView from "./views/DashboardView.vue"
import KnowledgeDocumentView from "./views/KnowledgeDocumentView.vue"
import KnowledgeView from "./views/KnowledgeView.vue"
import ForbiddenView from "./views/ForbiddenView.vue"
import InventoryView from "./views/InventoryView.vue"
import AgentRunDetailView from "./views/AgentRunDetailView.vue"
import AgentRunsView from "./views/AgentRunsView.vue"
import LoginView from "./views/LoginView.vue"
import NotFoundView from "./views/NotFoundView.vue"
import ProcurementDetailView from "./views/ProcurementDetailView.vue"
import ProcurementFormView from "./views/ProcurementFormView.vue"
import ProcurementsView from "./views/ProcurementsView.vue"
import SuppliersView from "./views/SuppliersView.vue"
import MCPToolsView from "./views/MCPToolsView.vue"
import WorkflowRunDetailView from "./views/WorkflowRunDetailView.vue"
import WorkflowRunsView from "./views/WorkflowRunsView.vue"

import type { Role } from "./api/types"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", name: "dashboard", component: DashboardView },
        { path: "assistant/:sessionId?", name: "assistant", component: AssistantView },
        { path: "knowledge", name: "knowledge", component: KnowledgeView },
        {
          path: "knowledge/documents/:documentId",
          name: "knowledge-document",
          component: KnowledgeDocumentView,
        },
        { path: "procurements", name: "procurements", component: ProcurementsView },
        { path: "procurements/new", name: "procurement-new", component: ProcurementFormView },
        {
          path: "procurements/:requestId",
          name: "procurement-detail",
          component: ProcurementDetailView,
        },
        { path: "inventory", name: "inventory", component: InventoryView },
        {
          path: "approvals",
          name: "approvals",
          component: ApprovalsView,
          meta: { roles: ["APPROVER"] satisfies Role[] },
        },
        {
          path: "approvals/:taskId",
          name: "approval-detail",
          component: ApprovalDetailView,
          meta: { roles: ["APPROVER"] satisfies Role[] },
        },
        {
          path: "admin/approval-rules",
          name: "approval-rules",
          component: ApprovalRulesView,
          meta: { roles: ["ADMIN"] satisfies Role[] },
        },
        {
          path: "suppliers",
          name: "suppliers",
          component: SuppliersView,
          meta: { roles: ["PROCUREMENT", "ADMIN"] satisfies Role[] },
        },
        {
          path: "workflows/runs",
          name: "workflow-runs",
          component: WorkflowRunsView,
          meta: { roles: ["TECH_ADMIN", "ADMIN"] satisfies Role[] },
        },
        {
          path: "workflows/runs/:runId",
          name: "workflow-run-detail",
          component: WorkflowRunDetailView,
          meta: { roles: ["TECH_ADMIN", "ADMIN"] satisfies Role[] },
        },
        {
          path: "tools/:toolId?",
          name: "mcp-tools",
          component: MCPToolsView,
          meta: { roles: ["TECH_ADMIN", "ADMIN"] satisfies Role[] },
        },
        {
          path: "agent-runs",
          name: "agent-runs",
          component: AgentRunsView,
          meta: { roles: ["TECH_ADMIN", "ADMIN"] satisfies Role[] },
        },
        {
          path: "agent-runs/:runId",
          name: "agent-run-detail",
          component: AgentRunDetailView,
          meta: { roles: ["TECH_ADMIN", "ADMIN"] satisfies Role[] },
        },
      ],
    },
    { path: "/403", name: "forbidden", component: ForbiddenView },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: NotFoundView,
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) {
    if (to.name === "login" && await auth.ensureLoaded()) return { name: "dashboard" }
    return true
  }
  if (await auth.ensureLoaded()) {
    const roles = to.meta.roles as Role[] | undefined
    if (roles && !roles.some(role => auth.user.value?.roles.includes(role))) {
      return { name: "forbidden" }
    }
    return true
  }
  return { name: "login", query: { redirect: to.fullPath } }
})

export default router
