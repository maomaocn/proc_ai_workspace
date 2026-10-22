<script setup lang="ts">
import { FilePlus2, Search } from "@lucide/vue"
import { computed, onMounted, ref } from "vue"

import { api, ApiError } from "../api/client"
import type { Procurement, PurchaseStatus } from "../api/types"
import MoneyDisplay from "../components/MoneyDisplay.vue"
import { auth } from "../auth/store"

const items = ref<Procurement[]>([])
const loading = ref(true)
const error = ref("")
const query = ref("")
const status = ref("")
const isProcurement = computed(() => auth.user.value?.roles.includes("PROCUREMENT"))

const statusLabels: Record<PurchaseStatus, string> = {
  DRAFT: "草稿",
  SUBMITTED: "已提交",
  PENDING_APPROVAL: "审批中",
  APPROVED: "已批准",
  REJECTED: "已驳回",
  ORDERED: "已下单",
  RECEIVED: "已收货",
  CLOSED: "已关闭",
  CANCELLED: "已取消",
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  const params = new URLSearchParams({ page: "1", page_size: "100" })
  if (query.value.trim()) params.set("query", query.value.trim())
  if (status.value) params.set("status", status.value)
  try {
    items.value = (await api.procurements(params.toString())).items
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取采购申请"
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="business-page">
    <header class="business-header">
      <div>
        <p class="overline">
          PURCHASE REQUESTS
        </p>
        <h1>{{ isProcurement ? "采购申请与履约" : "采购申请" }}</h1>
        <p>{{ isProcurement ? "查看本人申请和已授权的模拟履约单据。" : "查看本人采购草稿和候选方案；金额由服务端 Decimal 规则计算。" }}</p>
      </div>
      <RouterLink
        class="primary-button"
        to="/procurements/new"
      >
        <FilePlus2 :size="17" />
        新建采购草稿
      </RouterLink>
    </header>

    <form
      class="filter-bar"
      @submit.prevent="load"
    >
      <label>
        <span>关键字</span>
        <input
          v-model="query"
          placeholder="标题或品类"
        >
      </label>
      <label>
        <span>状态</span>
        <select v-model="status">
          <option value="">全部状态</option>
          <option value="DRAFT">草稿</option>
          <option value="PENDING_APPROVAL">审批中</option>
          <option value="APPROVED">已批准</option>
          <option value="REJECTED">已驳回</option>
          <option value="ORDERED">已下单</option>
          <option value="RECEIVED">已收货</option>
          <option value="CLOSED">已关闭</option>
          <option value="CANCELLED">已取消</option>
        </select>
      </label>
      <button
        class="secondary-button"
        type="submit"
      >
        <Search :size="16" />
        查询
      </button>
    </form>

    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-if="loading"
      class="business-state"
    >
      正在加载采购申请...
    </div>
    <div
      v-else-if="items.length === 0"
      class="business-state"
    >
      <h2>暂无采购申请</h2>
      <p>可以手工创建草稿，也可以在 AI 采购助手中确认结构化需求。</p>
    </div>
    <div
      v-else
      class="table-scroll"
    >
      <table class="business-table">
        <thead>
          <tr>
            <th>申请</th>
            <th>申请人</th>
            <th>数量</th>
            <th>预算</th>
            <th>状态</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.id"
          >
            <td>
              <RouterLink :to="`/procurements/${item.id}`">
                {{ item.title }}
              </RouterLink>
              <small>{{ item.category }}</small>
            </td>
            <td>{{ item.requester.username }}</td>
            <td>{{ item.quantity }}</td>
            <td><MoneyDisplay :value="item.total_budget" /></td>
            <td><span :class="['status-badge', item.status.toLowerCase()]">{{ statusLabels[item.status] }}</span></td>
            <td>{{ new Date(item.updated_at).toLocaleString("zh-CN", { hour12: false }) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
