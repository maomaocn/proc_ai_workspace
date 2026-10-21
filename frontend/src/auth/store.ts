import { computed, reactive } from "vue"

import { api } from "../api/client"
import type { User } from "../api/types"

const state = reactive<{ user: User | null; loading: boolean; initialized: boolean }>({
  user: null,
  loading: false,
  initialized: false,
})

async function login(username: string, password: string): Promise<void> {
  state.loading = true
  try {
    const response = await api.login(username, password)
    sessionStorage.setItem("access_token", response.access_token)
    state.user = response.user
    state.initialized = true
  } finally {
    state.loading = false
  }
}

async function ensureLoaded(): Promise<boolean> {
  if (state.initialized) return state.user !== null
  if (!sessionStorage.getItem("access_token")) {
    state.initialized = true
    return false
  }
  state.loading = true
  try {
    state.user = await api.me()
    return true
  } catch {
    sessionStorage.removeItem("access_token")
    state.user = null
    return false
  } finally {
    state.loading = false
    state.initialized = true
  }
}

function logout(): void {
  sessionStorage.removeItem("access_token")
  state.user = null
  state.initialized = true
}

export const auth = {
  state,
  user: computed(() => state.user),
  isAuthenticated: computed(() => state.user !== null),
  login,
  ensureLoaded,
  logout,
}
