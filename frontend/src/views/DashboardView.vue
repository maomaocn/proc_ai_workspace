<script setup lang="ts">
import { ArrowRight, MessageSquarePlus, ShieldCheck, Sparkles } from "@lucide/vue"
import { onMounted, ref } from "vue"

import { api, ApiError } from "../api/client"
import type { ChatSession } from "../api/types"
import { auth } from "../auth/store"

const sessions = ref<ChatSession[]>([])
const loading = ref(true)
const error = ref("")

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    sessions.value = (await api.sessions()).items.slice(0, 4)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取工作台数据"
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page dashboard-page">
    <header class="page-header dashboard-header">
      <div>
        <p class="overline">
          WORKSPACE
        </p>
        <h1>你好，{{ auth.user.value?.username }}</h1>
        <p>把采购需求整理成可确认的结构化信息。</p>
      </div>
      <RouterLink
        class="primary-button"
        to="/assistant"
      >
        <MessageSquarePlus :size="18" />
        发起采购对话
      </RouterLink>
    </header>

    <section
      class="workspace-band"
      aria-labelledby="workspace-summary"
    >
      <div>
        <p class="overline">
          CURRENT SCOPE
        </p>
        <h2 id="workspace-summary">
          身份已验证，Mock 模型已就绪
        </h2>
        <p>当前阶段支持会话、意图解析与人工确认，不会自动创建或提交采购申请。</p>
      </div>
      <div class="identity-summary">
        <span><ShieldCheck :size="18" />{{ auth.user.value?.department.name }}</span>
        <div class="role-list">
          <span
            v-for="role in auth.user.value?.roles"
            :key="role"
            class="role-chip"
          >{{ role }}</span>
        </div>
      </div>
    </section>

    <section
      class="recent-section"
      aria-labelledby="recent-heading"
    >
      <div class="section-title-row">
        <div>
          <p class="overline">
            RECENT SESSIONS
          </p>
          <h2 id="recent-heading">
            最近会话
          </h2>
        </div>
        <RouterLink
          class="text-link"
          to="/assistant"
        >
          查看全部 <ArrowRight :size="15" />
        </RouterLink>
      </div>

      <div
        v-if="loading"
        class="state-panel"
      >
        正在读取会话...
      </div>
      <div
        v-else-if="error"
        class="state-panel error-state"
      >
        <p>{{ error }}</p>
        <button
          class="secondary-button"
          type="button"
          @click="load"
        >
          重新加载
        </button>
      </div>
      <div
        v-else-if="sessions.length === 0"
        class="state-panel empty-state"
      >
        <Sparkles :size="22" />
        <p>还没有采购对话。</p>
        <RouterLink
          class="text-link"
          to="/assistant"
        >
          创建第一条会话
        </RouterLink>
      </div>
      <div
        v-else
        class="session-table"
        role="list"
      >
        <RouterLink
          v-for="session in sessions"
          :key="session.id"
          class="session-table-row"
          :to="`/assistant/${session.id}`"
          role="listitem"
        >
          <span>
            <strong>{{ session.title }}</strong>
            <small>{{ new Date(session.updated_at).toLocaleString("zh-CN", { hour12: false }) }}</small>
          </span>
          <ArrowRight :size="17" />
        </RouterLink>
      </div>
    </section>
  </div>
</template>
