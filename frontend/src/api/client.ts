import type {
  ApprovalDecisionResult,
  ApprovalInboxItem,
  ApprovalPreview,
  ApprovalRule,
  ApprovalTaskDetail,
  AgentRunDetail,
  AgentEvent,
  AgentRunSummary,
  ApiErrorBody,
  ChatMessage,
  ChatSession,
  ChatTurn,
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  KnowledgeSearchResponse,
  FulfillmentStatus,
  FulfillmentTransitionResult,
  InventoryItem,
  LoginResponse,
  MCPServer,
  MCPTool,
  MCPToolTestResult,
  Page,
  Procurement,
  ProcurementDraftInput,
  ProcurementPlan,
  ProcurementSubmission,
  PurchaseIntent,
  Supplier,
  SupplierQuote,
  User,
  WorkflowRunDetail,
} from "./types"

const apiRoot = `${import.meta.env.VITE_API_BASE_URL || "/api"}/api/v1`

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId?: string,
  ) {
    super(message)
  }
}

function token(): string | null {
  return sessionStorage.getItem("access_token")
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set("Accept", "application/json")
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json")
  const accessToken = token()
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)

  const response = await fetch(`${apiRoot}${path}`, { ...options, headers })
  if (!response.ok) {
    let body: ApiErrorBody = {}
    try {
      body = await response.json() as ApiErrorBody
    } catch {
      // Preserve a stable fallback for non-JSON proxy failures.
    }
    throw new ApiError(
      body.error?.message || `请求失败（HTTP ${response.status}）`,
      response.status,
      body.error?.code || "HTTP_ERROR",
      body.error?.request_id,
    )
  }
  return await response.json() as T
}

async function requestAgentEvents(runId: string, lastEventId = 0): Promise<AgentEvent[]> {
  const headers = new Headers({ Accept: "text/event-stream" })
  const accessToken = token()
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  if (lastEventId > 0) headers.set("Last-Event-ID", String(lastEventId))
  const response = await fetch(`${apiRoot}/agent-runs/${runId}/events`, { headers })
  if (!response.ok) {
    throw new ApiError(`运行事件读取失败（HTTP ${response.status}）`, response.status, "HTTP_ERROR")
  }
  const content = await response.text()
  return content.split("\n\n").flatMap((block) => {
    if (!block.trim()) return []
    const lines = block.split("\n")
    const event = lines.find(line => line.startsWith("event: "))?.slice(7) || "message"
    const rawData = lines.find(line => line.startsWith("data: "))?.slice(6)
    if (!rawData) return []
    const data = JSON.parse(rawData) as AgentEvent["data"]
    const rawId = lines.find(line => line.startsWith("id: "))?.slice(4)
    return [{ id: rawId ? Number(rawId) : data.seq, event, data }]
  })
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>("/auth/me"),
  sessions: () => request<Page<ChatSession>>("/chat/sessions?page=1&page_size=100"),
  createSession: (title = "新的采购对话") =>
    request<ChatSession>("/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  updateSession: (sessionId: string, payload: { title?: string; archived?: boolean }) =>
    request<ChatSession>(`/chat/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  messages: (sessionId: string) =>
    request<Page<ChatMessage>>(`/chat/sessions/${sessionId}/messages?page=1&page_size=100`),
  sendMessage: (sessionId: string, content: string) =>
    request<ChatTurn>(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  confirmIntent: (messageId: string, intent: PurchaseIntent) =>
    request<{ message: ChatMessage; confirmed_intent: PurchaseIntent; purchase_request_created: boolean; purchase_request_id: string }>(
      `/chat/messages/${messageId}/confirm-intent`,
      { method: "POST", body: JSON.stringify({ intent }) },
    ),
  knowledgeCollections: () => request<KnowledgeCollection[]>("/knowledge/collections"),
  knowledgeDocuments: (collectionId: string) =>
    request<Page<KnowledgeDocument>>(
      `/knowledge/documents?collection_id=${encodeURIComponent(collectionId)}&page=1&page_size=100`,
    ),
  knowledgeDocument: (documentId: string) =>
    request<KnowledgeDocumentDetail>(`/knowledge/documents/${documentId}`),
  uploadKnowledgeDocument: (collectionId: string, file: File) => {
    const body = new FormData()
    body.set("collection_id", collectionId)
    body.set("file", file)
    return request<KnowledgeDocument>("/knowledge/documents", { method: "POST", body })
  },
  reindexKnowledgeDocument: (documentId: string) =>
    request<KnowledgeDocument>(`/knowledge/documents/${documentId}/reindex`, { method: "POST" }),
  deleteKnowledgeDocument: (documentId: string) =>
    request<KnowledgeDocument>(`/knowledge/documents/${documentId}`, { method: "DELETE" }),
  searchKnowledge: (collectionId: string, query: string, topK: number) =>
    request<KnowledgeSearchResponse>("/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ collection_id: collectionId, query, top_k: topK }),
    }),
  procurements: (params = "page=1&page_size=100") =>
    request<Page<Procurement>>(`/procurements?${params}`),
  procurement: (requestId: string) => request<Procurement>(`/procurements/${requestId}`),
  createProcurement: (payload: ProcurementDraftInput) =>
    request<Procurement>("/procurements", { method: "POST", body: JSON.stringify(payload) }),
  updateProcurement: (requestId: string, payload: Partial<ProcurementDraftInput> & { version: number }) =>
    request<Procurement>(`/procurements/${requestId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  buildProcurementPlan: (requestId: string) =>
    request<ProcurementPlan>(`/procurements/${requestId}/plan`, { method: "POST" }),
  approvalPreview: (requestId: string) =>
    request<ApprovalPreview>(`/procurements/${requestId}/approval-preview`),
  submitProcurement: (requestId: string, version: number, idempotencyKey: string) =>
    request<ProcurementSubmission>(`/procurements/${requestId}/submit`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ version }),
    }),
  cancelProcurement: (requestId: string, version: number, idempotencyKey: string) =>
    request<{ request_id: string; purchase_status: "CANCELLED"; version: number }>(
      `/procurements/${requestId}/cancel`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ version }),
      },
    ),
  transitionFulfillment: (
    requestId: string,
    targetStatus: FulfillmentStatus,
    version: number,
    note: string | null,
    idempotencyKey: string,
  ) => request<FulfillmentTransitionResult>(
    `/procurements/${requestId}/fulfillment-transition`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ target_status: targetStatus, version, note }),
    },
  ),
  approvalTasks: (view: "pending" | "processed") =>
    request<Page<ApprovalInboxItem>>(`/approvals/tasks?view=${view}&page=1&page_size=100`),
  approvalTask: (taskId: string) => request<ApprovalTaskDetail>(`/approvals/tasks/${taskId}`),
  decideApproval: (
    taskId: string,
    payload: { action: "APPROVE" | "REJECT"; comment: string | null },
    idempotencyKey: string,
  ) => request<ApprovalDecisionResult>(`/approvals/tasks/${taskId}/decision`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  }),
  approvalRules: () => request<ApprovalRule[]>("/admin/approval-rules"),
  createApprovalRule: (payload: Omit<ApprovalRule, "id" | "created_at" | "updated_at">) =>
    request<ApprovalRule>("/admin/approval-rules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateApprovalRule: (ruleId: string, payload: Partial<ApprovalRule>) =>
    request<ApprovalRule>(`/admin/approval-rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  inventoryItems: (params = "page=1&page_size=100") =>
    request<Page<InventoryItem>>(`/inventory/items?${params}`),
  createInventoryItem: (payload: Omit<InventoryItem, "id" | "created_at" | "updated_at">) =>
    request<InventoryItem>("/inventory/items", { method: "POST", body: JSON.stringify(payload) }),
  updateInventoryItem: (itemId: string, payload: Partial<InventoryItem>) =>
    request<InventoryItem>(`/inventory/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  suppliers: () => request<Page<Supplier>>("/suppliers?page=1&page_size=100"),
  createSupplier: (payload: { name: string; active: boolean }) =>
    request<Supplier>("/suppliers", { method: "POST", body: JSON.stringify(payload) }),
  updateSupplier: (supplierId: string, payload: { name?: string; active?: boolean }) =>
    request<Supplier>(`/suppliers/${supplierId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  supplierQuotes: () => request<Page<SupplierQuote>>("/supplier-quotes?page=1&page_size=100"),
  createSupplierQuote: (payload: { supplier_id: string; inventory_item_id: string; unit_price: string; quoted_at: string }) =>
    request<SupplierQuote>("/supplier-quotes", { method: "POST", body: JSON.stringify(payload) }),
  agentRuns: (params = "page=1&page_size=100") =>
    request<Page<AgentRunSummary>>(`/agent-runs?${params}`),
  agentRun: (runId: string) => request<AgentRunDetail>(`/agent-runs/${runId}`),
  agentRunEvents: (runId: string, lastEventId = 0) => requestAgentEvents(runId, lastEventId),
  workflowRun: (runId: string) => request<WorkflowRunDetail>(`/workflows/runs/${runId}`),
  mcpServers: () => request<MCPServer[]>("/mcp/servers"),
  mcpTools: () => request<MCPTool[]>("/mcp/tools"),
  testMcpTool: (toolId: string, args: Record<string, unknown>) =>
    request<MCPToolTestResult>(`/mcp/tools/${toolId}/test`, {
      method: "POST",
      body: JSON.stringify({ arguments: args }),
    }),
}
