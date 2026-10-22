<script setup lang="ts">
import { ArrowLeft, Check, ShieldAlert, X } from "@lucide/vue"
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { api, ApiError } from "../api/client"
import type { ApprovalTaskDetail } from "../api/types"
import MoneyDisplay from "../components/MoneyDisplay.vue"

const route = useRoute()
const detail = ref<ApprovalTaskDetail | null>(null)
const loading = ref(true)
const deciding = ref(false)
const error = ref("")
const success = ref("")
const rejectReason = ref("")
const pendingKey = ref("")
const pendingSignature = ref("")

const taskId = computed(() => String(route.params.taskId || ""))
const canDecide = computed(() => detail.value?.task.status === "PENDING")

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    detail.value = await api.approvalTask(taskId.value)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取审批详情"
  } finally {
    loading.value = false
  }
}

async function decide(action: "APPROVE" | "REJECT"): Promise<void> {
  if (!detail.value || !canDecide.value || deciding.value) return
  const comment = action === "REJECT" ? rejectReason.value.trim() : null
  if (action === "REJECT" && (comment?.length || 0) < 5) {
    error.value = "驳回理由至少需要 5 个字符。"
    return
  }
  const label = action === "APPROVE" ? "批准" : "驳回"
  if (!window.confirm(`确认${label}“${detail.value.procurement.title}”？此操作会推进审批工作流。`)) return
  const signature = JSON.stringify({ action, comment })
  if (pendingSignature.value !== signature) {
    pendingKey.value = crypto.randomUUID()
    pendingSignature.value = signature
  }
  deciding.value = true
  error.value = ""
  success.value = ""
  try {
    const result = await api.decideApproval(taskId.value, { action, comment }, pendingKey.value)
    success.value = result.purchase_status === "PENDING_APPROVAL"
      ? "本级审批已完成，工作流已恢复并等待下一级审批。"
      : `审批已完成，采购申请状态为 ${result.purchase_status}。`
    pendingKey.value = ""
    pendingSignature.value = ""
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "审批操作失败"
  } finally {
    deciding.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="business-page approval-detail-page">
    <RouterLink
      class="back-link"
      to="/approvals"
    >
      <ArrowLeft :size="16" />返回审批列表
    </RouterLink>
    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-if="success"
      class="inline-success"
      role="status"
    >
      {{ success }}
    </div>
    <div
      v-if="loading"
      class="business-state"
    >
      正在加载审批详情...
    </div>
    <template v-else-if="detail">
      <header class="business-header">
        <div>
          <p class="overline">
            APPROVAL TASK · STAGE {{ detail.task.stage }}
          </p>
          <h1>{{ detail.procurement.title }}</h1>
          <p>{{ detail.procurement.requester.username }} · {{ detail.procurement.category }} · {{ detail.procurement.purpose }}</p>
        </div>
        <span :class="['status-badge', detail.task.status.toLowerCase()]">{{ detail.task.status }}</span>
      </header>

      <section class="procurement-summary-band">
        <div><span>数量</span><strong>{{ detail.procurement.quantity }}</strong></div>
        <div><span>单价上限</span><strong><MoneyDisplay :value="detail.procurement.unit_price_limit" /></strong></div>
        <div><span>总预算</span><strong><MoneyDisplay :value="detail.procurement.total_budget" /></strong></div>
        <div><span>采购状态</span><strong>{{ detail.procurement.status }}</strong></div>
      </section>

      <div class="approval-layout">
        <section class="approval-main">
          <div class="panel-heading">
            <div>
              <p class="overline">
                DEMO CANDIDATES
              </p><h2>候选采购方案</h2>
            </div><span>{{ detail.procurement.candidates.length }} 项</span>
          </div>
          <div class="approval-candidate-list">
            <div
              v-for="candidate in detail.procurement.candidates"
              :key="candidate.id"
            >
              <span><strong>{{ candidate.model }}</strong><small>{{ candidate.sku }} · {{ candidate.supplier_name }} · DEMO</small></span>
              <span>{{ candidate.quantity }} × <MoneyDisplay :value="candidate.unit_price" /></span>
              <strong><MoneyDisplay :value="candidate.total_price" /></strong>
            </div>
          </div>

          <div class="panel-heading approval-chain-heading">
            <div>
              <p class="overline">
                SEQUENTIAL REVIEW
              </p><h2>审批进度</h2>
            </div>
          </div>
          <ol class="approval-chain">
            <li
              v-for="item in detail.approval_chain"
              :key="item.id"
              :class="item.status.toLowerCase()"
            >
              <span class="stage-index">{{ item.stage }}</span>
              <span><strong>{{ item.assignee.username }}</strong><small>{{ item.approver_role }}</small></span>
              <span :class="['status-badge', item.status.toLowerCase()]">{{ item.status }}</span>
              <p v-if="item.decision_comment">
                {{ item.decision_comment }}
              </p>
            </li>
          </ol>
        </section>

        <aside class="decision-panel">
          <ShieldAlert :size="22" />
          <p class="overline">
            HUMAN DECISION
          </p>
          <h2>第 {{ detail.task.stage }} 级审批</h2>
          <p>批准后由 LangGraph 从 PostgreSQL checkpoint 恢复；驳回会立即终止后续级别。</p>
          <label><span>驳回理由（5–500 字）</span><textarea
            v-model="rejectReason"
            rows="5"
            maxlength="500"
            :disabled="!canDecide || deciding"
          /></label>
          <div class="decision-actions">
            <button
              class="danger-button"
              type="button"
              :disabled="!canDecide || deciding"
              @click="decide('REJECT')"
            >
              <X :size="17" />驳回
            </button>
            <button
              class="primary-button"
              type="button"
              :disabled="!canDecide || deciding"
              @click="decide('APPROVE')"
            >
              <Check :size="17" />{{ deciding ? "处理中" : "批准" }}
            </button>
          </div>
          <small v-if="!canDecide">该任务已处理，审批按钮已锁定。</small>
        </aside>
      </div>
    </template>
  </div>
</template>
