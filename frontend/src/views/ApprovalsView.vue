<script setup lang="ts">
import { ArrowRight, CheckCircle2, Clock3 } from "@lucide/vue"
import { onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { api, ApiError } from "../api/client"
import type { ApprovalInboxItem } from "../api/types"
import MoneyDisplay from "../components/MoneyDisplay.vue"

const route = useRoute()
const router = useRouter()
const items = ref<ApprovalInboxItem[]>([])
const loading = ref(true)
const error = ref("")
const view = ref<"pending" | "processed">(route.query.view === "processed" ? "processed" : "pending")

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    items.value = (await api.approvalTasks(view.value)).items
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取审批任务"
  } finally {
    loading.value = false
  }
}

async function changeView(next: "pending" | "processed"): Promise<void> {
  view.value = next
  await router.replace({ query: { view: next } })
}

watch(view, load)
onMounted(load)
</script>

<template>
  <div class="business-page approvals-page">
    <header class="business-header">
      <div>
        <p class="overline">
          HUMAN APPROVAL
        </p>
        <h1>我的审批</h1>
        <p>仅显示分配给当前账号的任务；多级审批按顺序激活。</p>
      </div>
      <span class="source-chip">LANGGRAPH · POSTGRES CHECKPOINT</span>
    </header>

    <div
      class="segmented-tabs"
      role="tablist"
      aria-label="审批任务分类"
    >
      <button
        type="button"
        :class="{ active: view === 'pending' }"
        role="tab"
        :aria-selected="view === 'pending'"
        @click="changeView('pending')"
      >
        <Clock3 :size="16" /> 待我审批
      </button>
      <button
        type="button"
        :class="{ active: view === 'processed' }"
        role="tab"
        :aria-selected="view === 'processed'"
        @click="changeView('processed')"
      >
        <CheckCircle2 :size="16" /> 已处理
      </button>
    </div>

    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
      <button
        class="text-button"
        type="button"
        @click="load"
      >
        重试
      </button>
    </div>
    <div
      v-else-if="loading"
      class="business-state"
    >
      正在读取审批任务...
    </div>
    <div
      v-else-if="items.length === 0"
      class="business-state"
    >
      {{ view === "pending" ? "当前没有待审批任务。" : "还没有已处理任务。" }}
    </div>
    <div
      v-else
      class="business-table-wrap"
    >
      <table class="business-table">
        <thead><tr><th>申请</th><th>申请人</th><th>金额</th><th>当前级别</th><th>任务状态</th><th>提交时间</th><th aria-label="操作" /></tr></thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.task.id"
          >
            <td><strong>{{ item.request_title }}</strong><small>{{ item.task.request_id.slice(0, 8).toUpperCase() }}</small></td>
            <td>{{ item.requester_username }}</td>
            <td><MoneyDisplay :value="item.total_budget" /></td>
            <td>第 {{ item.task.stage }} 级 · {{ item.task.approver_role }}</td>
            <td><span :class="['status-badge', item.task.status.toLowerCase()]">{{ item.task.status }}</span></td>
            <td>{{ new Date(item.submitted_at).toLocaleString("zh-CN", { hour12: false }) }}</td>
            <td>
              <RouterLink
                class="icon-link"
                :to="`/approvals/${item.task.id}`"
                title="查看审批详情"
                aria-label="查看审批详情"
              >
                <ArrowRight :size="17" />
              </RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
