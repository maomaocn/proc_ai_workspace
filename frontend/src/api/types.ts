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
