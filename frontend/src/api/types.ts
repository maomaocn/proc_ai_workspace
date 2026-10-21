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
