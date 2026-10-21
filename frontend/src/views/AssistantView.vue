<script setup lang="ts">
import { Archive, Bot, MessageSquarePlus, Send, UserRound } from "@lucide/vue"
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { api, ApiError } from "../api/client"
import type { ChatMessage, ChatSession, PurchaseIntent } from "../api/types"
import IntentDraftCard from "../components/IntentDraftCard.vue"

const route = useRoute()
const router = useRouter()
const sessions = ref<ChatSession[]>([])
const messages = ref<ChatMessage[]>([])
const input = ref("")
const loadingSessions = ref(true)
const loadingMessages = ref(false)
const sending = ref(false)
const confirmingId = ref("")
const error = ref("")

const activeSessionId = computed(() => typeof route.params.sessionId === "string"
  ? route.params.sessionId
  : "")
const activeSession = computed(() => sessions.value.find(item => item.id === activeSessionId.value))

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback
}

async function loadSessions(): Promise<void> {
  loadingSessions.value = true
  error.value = ""
  try {
    sessions.value = (await api.sessions()).items
  } catch (caught) {
    error.value = errorMessage(caught, "无法读取会话")
  } finally {
    loadingSessions.value = false
  }
}

async function loadMessages(sessionId: string): Promise<void> {
  loadingMessages.value = true
  error.value = ""
  try {
    messages.value = (await api.messages(sessionId)).items
  } catch (caught) {
    error.value = errorMessage(caught, "无法读取消息")
    messages.value = []
  } finally {
    loadingMessages.value = false
  }
}

async function createSession(): Promise<ChatSession> {
  const created = await api.createSession()
  sessions.value.unshift(created)
  await router.push(`/assistant/${created.id}`)
  return created
}

async function send(): Promise<void> {
  const content = input.value.trim()
  if (!content || sending.value) return
  sending.value = true
  error.value = ""
  try {
    const session = activeSession.value || await createSession()
    const response = await api.sendMessage(session.id, content)
    messages.value.push(response.user_message, response.assistant_message)
    input.value = ""
    if (session.title === "新的采购对话") {
      const updated = await api.updateSession(session.id, { title: content.slice(0, 28) })
      const index = sessions.value.findIndex(item => item.id === session.id)
      if (index >= 0) sessions.value[index] = updated
    }
  } catch (caught) {
    error.value = errorMessage(caught, "消息发送失败")
  } finally {
    sending.value = false
  }
}

async function confirmIntent(message: ChatMessage, intent: PurchaseIntent): Promise<void> {
  confirmingId.value = message.id
  error.value = ""
  try {
    const result = await api.confirmIntent(message.id, intent)
    const index = messages.value.findIndex(item => item.id === message.id)
    if (index >= 0) messages.value[index] = result.message
  } catch (caught) {
    error.value = errorMessage(caught, "采购意图确认失败")
  } finally {
    confirmingId.value = ""
  }
}

async function archiveActive(): Promise<void> {
  if (!activeSession.value) return
  try {
    await api.updateSession(activeSession.value.id, { archived: true })
    sessions.value = sessions.value.filter(item => item.id !== activeSession.value?.id)
    messages.value = []
    await router.push("/assistant")
  } catch (caught) {
    error.value = errorMessage(caught, "会话归档失败")
  }
}

watch(activeSessionId, async (sessionId) => {
  if (sessionId) await loadMessages(sessionId)
  else messages.value = []
})

onMounted(async () => {
  await loadSessions()
  if (activeSessionId.value) await loadMessages(activeSessionId.value)
})
</script>

<template>
  <div class="assistant-layout">
    <aside
      class="conversation-sidebar"
      aria-label="会话列表"
    >
      <div class="conversation-sidebar-heading">
        <div>
          <p class="overline">
            CONVERSATIONS
          </p>
          <h1>采购助手</h1>
        </div>
        <button
          class="icon-button bordered"
          type="button"
          title="新建会话"
          aria-label="新建会话"
          @click="createSession"
        >
          <MessageSquarePlus :size="18" />
        </button>
      </div>
      <div
        v-if="loadingSessions"
        class="compact-state"
      >
        正在加载...
      </div>
      <div
        v-else-if="sessions.length === 0"
        class="compact-state"
      >
        暂无会话
      </div>
      <nav
        v-else
        class="conversation-list"
        aria-label="历史会话"
      >
        <RouterLink
          v-for="session in sessions"
          :key="session.id"
          :to="`/assistant/${session.id}`"
        >
          <strong>{{ session.title }}</strong>
          <small>{{ new Date(session.updated_at).toLocaleDateString("zh-CN") }}</small>
        </RouterLink>
      </nav>
    </aside>

    <section class="chat-panel">
      <header class="chat-header">
        <div>
          <p class="overline">
            AI PROCUREMENT ASSISTANT
          </p>
          <h2>{{ activeSession?.title || "开始新的采购需求" }}</h2>
        </div>
        <button
          v-if="activeSession"
          class="icon-button bordered"
          type="button"
          title="归档会话"
          aria-label="归档当前会话"
          @click="archiveActive"
        >
          <Archive :size="18" />
        </button>
      </header>

      <div
        v-if="error"
        class="inline-error"
        role="alert"
      >
        {{ error }}
      </div>

      <div
        class="message-feed"
        aria-live="polite"
      >
        <div
          v-if="loadingMessages"
          class="state-panel"
        >
          正在恢复会话...
        </div>
        <div
          v-else-if="messages.length === 0"
          class="assistant-empty"
        >
          <span class="assistant-mark"><Bot :size="25" /></span>
          <h3>描述你的采购需求</h3>
          <p>包含品类、数量、单价预算和用途；缺少信息时助手会继续追问。</p>
        </div>
        <template v-else>
          <article
            v-for="message in messages"
            :key="message.id"
            :class="['message', message.sender.toLowerCase()]"
          >
            <span class="message-avatar">
              <UserRound
                v-if="message.sender === 'USER'"
                :size="17"
              />
              <Bot
                v-else
                :size="17"
              />
            </span>
            <div class="message-body">
              <div class="message-meta">
                <strong>{{ message.sender === "USER" ? "你" : "采购助手" }}</strong>
                <time>{{ new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }) }}</time>
              </div>
              <p>{{ message.content }}</p>
              <IntentDraftCard
                v-if="message.sender === 'ASSISTANT' && message.payload_json"
                :message="message"
                :busy="confirmingId === message.id"
                @confirm="confirmIntent(message, $event)"
              />
            </div>
          </article>
        </template>
      </div>

      <form
        class="composer"
        @submit.prevent="send"
      >
        <label for="assistant-input">采购需求</label>
        <div class="composer-control">
          <textarea
            id="assistant-input"
            v-model="input"
            maxlength="4000"
            rows="2"
            placeholder="例如：采购 10 台笔记本，每台预算 6000 元，用于研发办公"
            @keydown.ctrl.enter="send"
            @keydown.meta.enter="send"
          />
          <button
            class="send-button"
            type="submit"
            :disabled="!input.trim() || sending"
            aria-label="发送消息"
          >
            <Send :size="19" />
          </button>
        </div>
        <small>{{ input.length }}/4000 · Mock 模式结果可复现</small>
      </form>
    </section>
  </div>
</template>
