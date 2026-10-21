import type {
  ApiErrorBody,
  ChatMessage,
  ChatSession,
  ChatTurn,
  LoginResponse,
  Page,
  PurchaseIntent,
  User,
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
  if (options.body) headers.set("Content-Type", "application/json")
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
    request<{ message: ChatMessage; confirmed_intent: PurchaseIntent; purchase_request_created: false }>(
      `/chat/messages/${messageId}/confirm-intent`,
      { method: "POST", body: JSON.stringify({ intent }) },
    ),
}
