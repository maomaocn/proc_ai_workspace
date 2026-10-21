<script setup lang="ts">
import { Activity, Database, RefreshCw, Server } from "@lucide/vue"
import { computed, onMounted, ref } from "vue"

type ProbeState = "checking" | "online" | "degraded" | "offline"

interface ProbeResult {
  state: ProbeState
  detail: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
const checkedAt = ref<Date | null>(null)
const isRefreshing = ref(false)
const apiProbe = ref<ProbeResult>({ state: "checking", detail: "正在检查 API" })
const databaseProbe = ref<ProbeResult>({ state: "checking", detail: "正在检查 PostgreSQL" })

const overallState = computed<ProbeState>(() => {
  if (apiProbe.value.state === "checking" || databaseProbe.value.state === "checking") {
    return "checking"
  }
  if (apiProbe.value.state === "online" && databaseProbe.value.state === "online") {
    return "online"
  }
  if (apiProbe.value.state === "offline") {
    return "offline"
  }
  return "degraded"
})

const overallLabel = computed(() => {
  const labels: Record<ProbeState, string> = {
    checking: "正在检查",
    online: "本地环境运行正常",
    degraded: "依赖尚未就绪",
    offline: "API 无法访问",
  }
  return labels[overallState.value]
})

const checkedAtLabel = computed(() =>
  checkedAt.value
    ? checkedAt.value.toLocaleTimeString("zh-CN", { hour12: false })
    : "等待首次检查",
)

async function requestJson(path: string): Promise<{ response: Response; data: unknown }> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
  })
  const data: unknown = await response.json()
  return { response, data }
}

async function refreshStatus(): Promise<void> {
  isRefreshing.value = true
  apiProbe.value = { state: "checking", detail: "正在检查 API" }
  databaseProbe.value = { state: "checking", detail: "正在检查 PostgreSQL" }

  try {
    const health = await requestJson("/healthz")
    apiProbe.value = health.response.ok
      ? { state: "online", detail: "FastAPI 已响应" }
      : { state: "offline", detail: `HTTP ${health.response.status}` }
  } catch {
    apiProbe.value = { state: "offline", detail: "无法连接 FastAPI" }
    databaseProbe.value = { state: "offline", detail: "等待 API 恢复" }
    checkedAt.value = new Date()
    isRefreshing.value = false
    return
  }

  try {
    const readiness = await requestJson("/readyz")
    databaseProbe.value = readiness.response.ok
      ? { state: "online", detail: "连接与查询成功" }
      : { state: "degraded", detail: `HTTP ${readiness.response.status}` }
  } catch {
    databaseProbe.value = { state: "degraded", detail: "就绪检查失败" }
  } finally {
    checkedAt.value = new Date()
    isRefreshing.value = false
  }
}

onMounted(refreshStatus)
</script>

<template>
  <main class="shell">
    <header class="masthead">
      <div class="brand-lockup">
        <span
          class="brand-mark"
          aria-hidden="true"
        >EA</span>
        <div>
          <p class="eyebrow">
            Enterprise Operations
          </p>
          <h1>Enterprise AI Agent Hub</h1>
        </div>
      </div>
      <span class="milestone">M0 / Foundation</span>
    </header>

    <section
      class="status-hero"
      aria-labelledby="environment-heading"
    >
      <div>
        <p class="section-index">
          Local environment
        </p>
        <h2 id="environment-heading">
          {{ overallLabel }}
        </h2>
        <p class="summary">
          FastAPI、PostgreSQL 与 Vue 工作台已连接到同一套可复现的本地运行环境。
        </p>
      </div>
      <div class="hero-meta">
        <span
          class="signal"
          :data-state="overallState"
        >
          <span class="signal-dot" />
          {{ overallState }}
        </span>
        <p>上次检查 {{ checkedAtLabel }}</p>
      </div>
    </section>

    <section
      class="service-section"
      aria-labelledby="services-heading"
    >
      <div class="section-heading">
        <div>
          <p class="section-index">
            Runtime checks
          </p>
          <h2 id="services-heading">
            服务状态
          </h2>
        </div>
        <button
          class="refresh-button"
          type="button"
          :disabled="isRefreshing"
          title="刷新服务状态"
          @click="refreshStatus"
        >
          <RefreshCw
            :class="{ spinning: isRefreshing }"
            :size="18"
            aria-hidden="true"
          />
          <span>刷新</span>
        </button>
      </div>

      <div class="service-list">
        <article class="service-row">
          <span class="service-icon"><Server
            :size="22"
            aria-hidden="true"
          /></span>
          <div class="service-copy">
            <h3>FastAPI</h3>
            <p>{{ apiProbe.detail }}</p>
          </div>
          <span
            class="state-label"
            :data-state="apiProbe.state"
          >{{ apiProbe.state }}</span>
        </article>

        <article class="service-row">
          <span class="service-icon"><Database
            :size="22"
            aria-hidden="true"
          /></span>
          <div class="service-copy">
            <h3>PostgreSQL</h3>
            <p>{{ databaseProbe.detail }}</p>
          </div>
          <span
            class="state-label"
            :data-state="databaseProbe.state"
          >
            {{ databaseProbe.state }}
          </span>
        </article>

        <article class="service-row">
          <span class="service-icon"><Activity
            :size="22"
            aria-hidden="true"
          /></span>
          <div class="service-copy">
            <h3>AI Providers</h3>
            <p>Mock LLM 与 Mock Embedding</p>
          </div>
          <span
            class="state-label"
            data-state="online"
          >mock</span>
        </article>
      </div>
    </section>

    <footer>
      <span>Environment: local</span>
      <a
        :href="`${apiBaseUrl}/docs`"
        target="_blank"
        rel="noreferrer"
      >OpenAPI</a>
    </footer>
  </main>
</template>
