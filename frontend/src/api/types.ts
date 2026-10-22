export type Role = "EMPLOYEE" | "APPROVER" | "PROCUREMENT" | "ADMIN" | "TECH_ADMIN"

export interface Department {
  id: string
  name: string
}

export interface User {
  id: string
  username: string
  department: Department
  roles: Role[]
  is_active: boolean
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: "bearer"
  expires_at: string
  user: User
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface ChatSession {
  id: string
  owner_id: string
  title: string
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface PurchaseIntent {
  category: string | null
  item_description: string | null
  quantity: number | null
  unit_price_limit: string | null
  total_budget: string | null
  purpose: string | null
  priority: "LOW" | "NORMAL" | "HIGH"
  notes: string | null
}

export interface IntentParseResult {
  intent: PurchaseIntent
  missing_fields: string[]
  follow_up_question: string | null
  requires_confirmation: boolean
  source: "MOCK" | "OPENAI_COMPATIBLE"
}

export interface ChatMessage {
  id: string
  session_id: string
  sender: "USER" | "ASSISTANT"
  content: string
  status: "COMPLETED" | "FAILED" | "CONFIRMED"
  run_id: string | null
  payload_json: (IntentParseResult & {
    confirmed_intent?: PurchaseIntent
    confirmed_at?: string
    purchase_request_id?: string
  }) | null
  created_at: string
}

export interface ChatTurn {
  run_id: string
  user_message: ChatMessage
  assistant_message: ChatMessage
  parse_result: IntentParseResult
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    request_id?: string
    details?: Record<string, unknown>
  }
}

export type KnowledgePermission = "READ" | "WRITE" | "ADMIN"
export type DocumentStatus = "PENDING" | "INDEXING" | "READY" | "FAILED" | "DELETED"

export interface KnowledgeCollection {
  id: string
  name: string
  visibility: "PRIVATE" | "INTERNAL"
  effective_permission: KnowledgePermission
  document_count: number
  created_at: string
  updated_at: string
}

export interface UploaderSummary {
  id: string
  username: string
}

export interface KnowledgeDocument {
  id: string
  collection_id: string
  filename: string
  sha256: string
  mime_type: string
  size_bytes: number
  status: DocumentStatus
  uploaded_by: string
  uploader: UploaderSummary
  index_version: number
  error_code: string | null
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeChunk {
  id: string
  chunk_index: number
  content: string
  page_number: number | null
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  chunks: KnowledgeChunk[]
}

export interface SearchHit {
  document_id: string
  filename: string
  chunk_id: string
  page_number: number | null
  snippet: string
  score: number
}

export interface KnowledgeSearchResponse {
  hits: SearchHit[]
  answer: string
  source: "MOCK" | "REMOTE"
  has_sufficient_evidence: boolean
}

export interface InventoryItem {
  id: string
  sku: string
  category: string
  model: string
  available_qty: number
  reference_price: string
  active: boolean
  created_at: string
  updated_at: string
}

export interface Supplier {
  id: string
  name: string
  active: boolean
  demo_data: boolean
  created_at: string
  updated_at: string
}

export interface SupplierQuote {
  id: string
  supplier_id: string
  inventory_item_id: string
  unit_price: string
  currency: "CNY"
  quoted_at: string
  source_type: "DEMO"
  supplier: Pick<Supplier, "id" | "name" | "active" | "demo_data">
  inventory_item: Pick<InventoryItem, "id" | "sku" | "category" | "model" | "available_qty" | "reference_price" | "active">
  created_at: string
}

export type PurchaseStatus = "DRAFT" | "SUBMITTED" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "ORDERED" | "RECEIVED" | "CLOSED" | "CANCELLED"
export type ApprovalTaskStatus = "WAITING" | "PENDING" | "APPROVED" | "REJECTED" | "SKIPPED"

export interface ProcurementDraftInput {
  title: string
  category: string
  item_description: string
  quantity: number
  unit_price_limit: string
  total_budget?: string
  purpose: string
  priority: "LOW" | "NORMAL" | "HIGH"
  notes: string | null
}

export interface PurchaseCandidate {
  id: string
  request_id: string
  item_id: string
  supplier_id: string
  quantity: number
  unit_price: string
  total_price: string
  source_quote_id: string
  item: Pick<InventoryItem, "id" | "sku" | "category" | "model" | "available_qty" | "reference_price" | "active">
  supplier: Pick<Supplier, "id" | "name" | "active" | "demo_data">
  source_quote: SupplierQuote
  stock_sufficient: boolean
  within_unit_limit: boolean
  within_total_budget: boolean
}

export interface Procurement {
  id: string
  requester_id: string
  requester: { id: string; username: string }
  title: string
  category: string
  item_description: string
  quantity: number
  unit_price_limit: string
  total_budget: string
  purpose: string
  priority: "LOW" | "NORMAL" | "HIGH"
  notes: string | null
  status: PurchaseStatus
  version: number
  linked_run_id: string | null
  candidates?: PurchaseCandidate[]
  approval_tasks?: ApprovalTask[]
  workflow_run?: WorkflowRun | null
  audit_events?: AuditEvent[]
  created_at: string
  updated_at: string
}

export interface ApprovalUser {
  id: string
  username: string
}

export interface ApprovalDecision {
  id: string
  task_id: string
  actor_id: string
  actor: ApprovalUser
  action: "APPROVE" | "REJECT"
  comment: string | null
  idempotency_key: string
  created_at: string
}

export interface ApprovalTask {
  id: string
  request_id: string
  stage: number
  approver_role: string
  assignee_id: string
  assignee: ApprovalUser
  status: ApprovalTaskStatus
  decision_comment: string | null
  decided_at: string | null
  created_at: string
  updated_at: string
  decisions: ApprovalDecision[]
}

export interface ApprovalInboxItem {
  task: ApprovalTask
  request_title: string
  requester_username: string
  total_budget: string
  purchase_status: PurchaseStatus
  submitted_at: string
}

export interface ApprovalCandidate {
  id: string
  sku: string
  model: string
  supplier_name: string
  quantity: number
  unit_price: string
  total_price: string
  source_type: "DEMO"
}

export interface ApprovalPurchase {
  id: string
  requester_id: string
  requester: ApprovalUser
  title: string
  category: string
  item_description: string
  quantity: number
  unit_price_limit: string
  total_budget: string
  purpose: string
  priority: "LOW" | "NORMAL" | "HIGH"
  notes: string | null
  status: PurchaseStatus
  version: number
  linked_run_id: string | null
  candidates: ApprovalCandidate[]
  created_at: string
  updated_at: string
}

export interface ApprovalTaskDetail {
  task: ApprovalTask
  procurement: ApprovalPurchase
  approval_chain: ApprovalTask[]
}

export interface ApprovalPreviewStage {
  stage: number
  approver_role: string
  assignee_id: string
  assignee_username: string
  assignee_department: string
}

export interface ApprovalPreview {
  request_id: string
  total_budget: string
  stages: ApprovalPreviewStage[]
}

export interface WorkflowRun {
  id: string
  request_id: string
  graph_thread_id: string
  status: string
  started_at: string
  finished_at: string | null
  error_code: string | null
  model_provider: string
  checkpoint?: Record<string, unknown> | null
}

export interface AuditEvent {
  id: string
  actor_id: string | null
  action: string
  resource_type: string
  resource_id: string
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  request_id: string
  created_at: string
}

export interface ProcurementSubmission {
  request_id: string
  purchase_status: PurchaseStatus
  version: number
  run: WorkflowRun
  approval_tasks: ApprovalTask[]
}

export interface ApprovalDecisionResult {
  task_id: string
  task_status: ApprovalTaskStatus
  purchase_status: PurchaseStatus
  decision_id: string
  workflow_run_id: string
  next_task_id: string | null
  idempotent_replay: boolean
}

export interface ApprovalRule {
  id: string
  min_amount: string
  max_amount: string | null
  stage: number
  approver_role: "APPROVER"
  active: boolean
  created_at: string
  updated_at: string
}

export interface ProcurementPlan {
  procurement: Procurement & { candidates: PurchaseCandidate[] }
  policy: KnowledgeSearchResponse
  tool_calls: Array<{
    name: string
    duration_ms: number
    source: "DATABASE" | "MOCK_RAG"
    item_count: number
  }>
  source: "DEMO"
}
