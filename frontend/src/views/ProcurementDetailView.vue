<script setup lang="ts">
import {
  ArrowLeft,
  CheckCircle2,
  GitBranch,
  PackageCheck,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  Truck,
  XCircle,
} from "@lucide/vue"
import { computed, onMounted, reactive, ref } from "vue"
import { useRoute } from "vue-router"

import { api, ApiError } from "../api/client"
import type {
  ApprovalPreview,
  FulfillmentStatus,
  Procurement,
  ProcurementPlan,
  PurchaseStatus,
} from "../api/types"
import { auth } from "../auth/store"
import MoneyDisplay from "../components/MoneyDisplay.vue"
import SourceCitation from "../components/SourceCitation.vue"

const route = useRoute()
const request = ref<Procurement | null>(null)
const plan = ref<ProcurementPlan | null>(null)
const loading = ref(true)
const saving = ref(false)
const planning = ref(false)
const submitting = ref(false)
const cancelling = ref(false)
const fulfilling = ref(false)
const fulfillmentDialogOpen = ref(false)
const fulfillmentKey = ref("")
const fulfillmentNote = ref("")
const submitDialogOpen = ref(false)
const approvalPreview = ref<ApprovalPreview | null>(null)
const submitKey = ref("")
const cancelKey = ref("")
const error = ref("")
const success = ref("")
const form = reactive({
  title: "",
  category: "",
  item_description: "",
  quantity: 1,
  unit_price_limit: "",
  purpose: "",
  priority: "NORMAL" as "LOW" | "NORMAL" | "HIGH",
  notes: "",
})

const requestId = computed(() => String(route.params.requestId || ""))
const canEdit = computed(() => request.value?.status === "DRAFT"
  && request.value.requester_id === auth.user.value?.id)
const canSubmit = computed(() => canEdit.value && request.value?.candidates?.some(
  candidate => candidate.stock_sufficient && candidate.within_unit_limit && candidate.within_total_budget,
))
const fulfillmentStatuses: PurchaseStatus[] = ["APPROVED", "ORDERED", "RECEIVED", "CLOSED"]
const fulfillmentSteps: FulfillmentStatus[] = ["ORDERED", "RECEIVED", "CLOSED"]
const nextFulfillmentStatus = computed<FulfillmentStatus | null>(() => {
  const current = request.value?.status
  if (current === "APPROVED") return "ORDERED"
  if (current === "ORDERED") return "RECEIVED"
  if (current === "RECEIVED") return "CLOSED"
  return null
})
const canFulfill = computed(() => Boolean(
  nextFulfillmentStatus.value && auth.user.value?.roles.includes("PROCUREMENT"),
))
const showFulfillment = computed(() => request.value
  ? fulfillmentStatuses.includes(request.value.status)
  : false)
const fulfillmentLabels: Record<FulfillmentStatus, string> = {
  ORDERED: "确认模拟下单",
  RECEIVED: "确认模拟收货",
  CLOSED: "关闭采购单",
}

function fulfillmentStepState(step: FulfillmentStatus): "done" | "current" | "pending" {
  const currentIndex = fulfillmentStatuses.indexOf(request.value?.status || "APPROVED")
  const stepIndex = fulfillmentStatuses.indexOf(step)
  if (stepIndex <= currentIndex) return "done"
  if (stepIndex === currentIndex + 1) return "current"
  return "pending"
}

function fillForm(item: Procurement): void {
  form.title = item.title
  form.category = item.category
  form.item_description = item.item_description
  form.quantity = item.quantity
  form.unit_price_limit = item.unit_price_limit
  form.purpose = item.purpose
  form.priority = item.priority
  form.notes = item.notes || ""
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    request.value = await api.procurement(requestId.value)
    fillForm(request.value)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取采购申请"
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (!request.value || !canEdit.value || saving.value) return
  saving.value = true
  error.value = ""
  success.value = ""
  try {
    request.value = await api.updateProcurement(request.value.id, {
      version: request.value.version,
      ...form,
      notes: form.notes.trim() || null,
    })
    plan.value = null
    fillForm(request.value)
    success.value = "采购草稿已保存，旧候选方案已清除。"
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "采购草稿保存失败"
  } finally {
    saving.value = false
  }
}

async function buildPlan(): Promise<void> {
  if (!request.value || !canEdit.value || planning.value) return
  planning.value = true
  error.value = ""
  success.value = ""
  try {
    plan.value = await api.buildProcurementPlan(request.value.id)
    request.value = plan.value.procurement
    success.value = `已通过 ${plan.value.tool_calls.length} 次只读工具调用生成候选方案。`
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "候选方案生成失败"
  } finally {
    planning.value = false
  }
}

async function openSubmitDialog(): Promise<void> {
  if (!request.value || !canSubmit.value) return
  error.value = ""
  try {
    approvalPreview.value = await api.approvalPreview(request.value.id)
    submitDialogOpen.value = true
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法预览审批链"
  }
}

async function submitForApproval(): Promise<void> {
  if (!request.value || !canSubmit.value || submitting.value) return
  submitting.value = true
  error.value = ""
  success.value = ""
  submitKey.value ||= crypto.randomUUID()
  try {
    await api.submitProcurement(request.value.id, request.value.version, submitKey.value)
    submitDialogOpen.value = false
    submitKey.value = ""
    success.value = "采购申请已提交，审批工作流正在等待第一级人工决策。"
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "采购申请提交失败"
  } finally {
    submitting.value = false
  }
}

async function cancelDraft(): Promise<void> {
  if (!request.value || !canEdit.value || cancelling.value) return
  if (!window.confirm(`确认取消草稿“${request.value.title}”？取消后不可继续编辑或提交。`)) return
  cancelling.value = true
  error.value = ""
  success.value = ""
  cancelKey.value ||= crypto.randomUUID()
  try {
    await api.cancelProcurement(request.value.id, request.value.version, cancelKey.value)
    cancelKey.value = ""
    success.value = "采购草稿已取消。"
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "采购草稿取消失败"
  } finally {
    cancelling.value = false
  }
}

function openFulfillmentDialog(): void {
  if (!canFulfill.value) return
  fulfillmentNote.value = ""
  fulfillmentDialogOpen.value = true
}

async function advanceFulfillment(): Promise<void> {
  if (!request.value || !nextFulfillmentStatus.value || !canFulfill.value || fulfilling.value) return
  fulfilling.value = true
  error.value = ""
  success.value = ""
  fulfillmentKey.value ||= crypto.randomUUID()
  const target = nextFulfillmentStatus.value
  try {
    await api.transitionFulfillment(
      request.value.id,
      target,
      request.value.version,
      fulfillmentNote.value.trim() || null,
      fulfillmentKey.value,
    )
    fulfillmentKey.value = ""
    fulfillmentDialogOpen.value = false
    success.value = `模拟履约状态已更新为 ${target}。`
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "采购履约状态更新失败"
  } finally {
    fulfilling.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="business-page">
    <RouterLink
      class="back-link"
      to="/procurements"
    >
      <ArrowLeft :size="16" />
      返回采购列表
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
      正在加载采购详情...
    </div>
    <template v-else-if="request">
      <header class="business-header procurement-detail-header">
        <div>
          <p class="overline">
            PURCHASE REQUEST · {{ request.id.slice(0, 8).toUpperCase() }}
          </p>
          <h1>{{ request.title }}</h1>
          <p>{{ request.requester.username }} · 版本 {{ request.version }} · {{ request.status === "DRAFT" ? "尚未提交审批" : request.status }}</p>
        </div>
        <div class="header-actions">
          <span :class="['status-badge', request.status.toLowerCase()]">{{ request.status === "DRAFT" ? "草稿" : request.status }}</span>
          <button
            v-if="canEdit"
            class="danger-text-button"
            type="button"
            :disabled="cancelling"
            @click="cancelDraft"
          >
            <XCircle :size="16" />{{ cancelling ? "取消中" : "取消草稿" }}
          </button>
          <button
            v-if="canEdit"
            class="primary-button"
            type="button"
            :disabled="!canSubmit || submitting"
            @click="openSubmitDialog"
          >
            <Send :size="16" />提交审批
          </button>
        </div>
      </header>

      <section class="procurement-summary-band">
        <div><span>数量</span><strong>{{ request.quantity }}</strong></div>
        <div><span>单价上限</span><strong><MoneyDisplay :value="request.unit_price_limit" /></strong></div>
        <div><span>服务端总预算</span><strong><MoneyDisplay :value="request.total_budget" /></strong></div>
        <div><span>候选方案</span><strong>{{ request.candidates?.length || 0 }}</strong></div>
      </section>

      <section
        v-if="showFulfillment"
        class="fulfillment-band"
      >
        <div class="fulfillment-copy">
          <p class="overline">
            DEMO FULFILLMENT
          </p>
          <h2>采购履约</h2>
          <p>本地模拟状态，不会连接供应商、付款系统或真实 ERP。</p>
        </div>
        <ol
          class="fulfillment-track"
          aria-label="采购履约进度"
        >
          <li class="done">
            <CheckCircle2 :size="18" />
            <span><strong>已批准</strong><small>APPROVED</small></span>
          </li>
          <li
            v-for="step in fulfillmentSteps"
            :key="step"
            :class="fulfillmentStepState(step)"
          >
            <CheckCircle2
              v-if="fulfillmentStepState(step) === 'done'"
              :size="18"
            />
            <span
              v-else
              class="track-marker"
            />
            <span><strong>{{ step === 'ORDERED' ? '已下单' : step === 'RECEIVED' ? '已收货' : '已关闭' }}</strong><small>{{ step }}</small></span>
          </li>
        </ol>
        <div class="fulfillment-action">
          <button
            v-if="canFulfill && nextFulfillmentStatus"
            class="primary-button"
            type="button"
            :disabled="fulfilling"
            @click="openFulfillmentDialog"
          >
            <Truck
              v-if="nextFulfillmentStatus === 'ORDERED'"
              :size="17"
            />
            <PackageCheck
              v-else
              :size="17"
            />
            {{ fulfillmentLabels[nextFulfillmentStatus] }}
          </button>
          <small v-else-if="request.status === 'CLOSED'">履约流程已完成。</small>
          <small v-else>等待采购人员推进下一状态。</small>
        </div>
      </section>

      <div class="procurement-detail-grid">
        <section class="procurement-editor">
          <div class="panel-heading">
            <div>
              <p class="overline">
                REQUIREMENTS
              </p><h2>采购需求</h2>
            </div>
            <button
              v-if="canEdit"
              class="secondary-button"
              type="button"
              :disabled="saving"
              @click="save"
            >
              <Save :size="16" /> {{ saving ? "保存中" : "保存修改" }}
            </button>
          </div>
          <form
            class="business-form detail-form"
            @submit.prevent="save"
          >
            <label><span>标题</span><input
              v-model.trim="form.title"
              :disabled="!canEdit"
            ></label>
            <label><span>品类</span><input
              v-model.trim="form.category"
              :disabled="!canEdit"
            ></label>
            <label class="wide-field"><span>商品描述</span><input
              v-model.trim="form.item_description"
              :disabled="!canEdit"
            ></label>
            <label><span>数量</span><input
              v-model.number="form.quantity"
              type="number"
              min="1"
              :disabled="!canEdit"
            ></label>
            <label><span>单价上限（元）</span><input
              v-model="form.unit_price_limit"
              type="number"
              min="0.01"
              step="0.01"
              :disabled="!canEdit"
            ></label>
            <label><span>优先级</span><select
              v-model="form.priority"
              :disabled="!canEdit"
            ><option value="LOW">低</option><option value="NORMAL">普通</option><option value="HIGH">高</option></select></label>
            <label class="wide-field"><span>用途</span><textarea
              v-model.trim="form.purpose"
              rows="3"
              :disabled="!canEdit"
            /></label>
            <label class="wide-field"><span>备注</span><textarea
              v-model="form.notes"
              rows="3"
              :disabled="!canEdit"
            /></label>
          </form>
        </section>

        <aside class="plan-control-panel">
          <p class="overline">
            READ-ONLY TOOL CALLING
          </p>
          <h2>采购方案</h2>
          <p>从本地数据库查询库存和 DEMO 报价，并在授权知识库中检索制度依据。</p>
          <button
            class="primary-button"
            type="button"
            :disabled="!canEdit || planning"
            @click="buildPlan"
          >
            <RefreshCw
              v-if="planning"
              :size="17"
              class="spinning"
            />
            <Sparkles
              v-else
              :size="17"
            />
            {{ planning ? "正在调用工具" : "生成候选方案" }}
          </button>
          <small v-if="canEdit && !canSubmit">至少需要一个库存充足且预算内的候选方案，才能提交审批。</small>
          <small v-else-if="!canEdit">只有申请人可为草稿生成方案。</small>
          <div
            v-if="plan"
            class="tool-call-list"
          >
            <div
              v-for="tool in plan.tool_calls"
              :key="`${tool.name}-${tool.duration_ms}`"
            >
              <strong>{{ tool.name }}</strong>
              <span>{{ tool.source }} · {{ tool.item_count }} 项 · {{ tool.duration_ms }}ms</span>
            </div>
          </div>
        </aside>
      </div>

      <section class="candidate-section">
        <div class="panel-heading">
          <div>
            <p class="overline">
              CANDIDATES · DEMO
            </p><h2>候选商品与报价</h2>
          </div><span>{{ request.candidates?.length || 0 }} 项</span>
        </div>
        <div
          v-if="!request.candidates?.length"
          class="business-state compact"
        >
          尚未生成候选方案。
        </div>
        <div
          v-else
          class="candidate-grid"
        >
          <article
            v-for="candidate in request.candidates"
            :key="candidate.id"
            class="candidate-card"
          >
            <header><div><small>{{ candidate.item.sku }}</small><h3>{{ candidate.item.model }}</h3></div><span class="demo-badge">DEMO</span></header>
            <dl>
              <div><dt>供应商</dt><dd>{{ candidate.supplier.name }}</dd></div>
              <div><dt>库存</dt><dd>{{ candidate.item.available_qty }} / 需 {{ candidate.quantity }}</dd></div>
              <div><dt>报价单价</dt><dd><MoneyDisplay :value="candidate.unit_price" /></dd></div>
              <div><dt>方案总价</dt><dd><MoneyDisplay :value="candidate.total_price" /></dd></div>
            </dl>
            <div class="candidate-checks">
              <span :class="candidate.stock_sufficient ? 'ok' : 'risk'">{{ candidate.stock_sufficient ? "库存充足" : "库存不足" }}</span>
              <span :class="candidate.within_unit_limit && candidate.within_total_budget ? 'ok' : 'risk'">{{ candidate.within_unit_limit && candidate.within_total_budget ? "预算内" : "超出预算" }}</span>
            </div>
          </article>
        </div>
      </section>

      <section
        v-if="plan"
        class="policy-section"
      >
        <div class="panel-heading">
          <div>
            <p class="overline">
              POLICY EVIDENCE
            </p><h2>制度依据</h2>
          </div><span>{{ plan.policy.hits.length }} 条</span>
        </div>
        <div :class="['answer-box', { empty: !plan.policy.has_sufficient_evidence }]">
          <p>{{ plan.policy.answer }}</p>
        </div>
        <div class="citation-list">
          <SourceCitation
            v-for="hit in plan.policy.hits"
            :key="hit.chunk_id"
            :hit="hit"
          />
        </div>
      </section>

      <section
        v-if="request.approval_tasks?.length"
        class="workflow-section"
      >
        <div class="panel-heading">
          <div>
            <p class="overline">
              LANGGRAPH WORKFLOW
            </p><h2>审批进度</h2>
          </div>
          <span>{{ request.workflow_run?.status || request.status }}</span>
        </div>
        <ol class="approval-chain horizontal-chain">
          <li
            v-for="task in request.approval_tasks"
            :key="task.id"
            :class="task.status.toLowerCase()"
          >
            <span class="stage-index">{{ task.stage }}</span>
            <span><strong>{{ task.assignee.username }}</strong><small>{{ task.approver_role }}</small></span>
            <span :class="['status-badge', task.status.toLowerCase()]">{{ task.status }}</span>
            <p v-if="task.decision_comment">
              {{ task.decision_comment }}
            </p>
          </li>
        </ol>
        <p
          v-if="request.workflow_run"
          class="workflow-meta"
        >
          <GitBranch :size="15" />运行 {{ request.workflow_run.id.slice(0, 8).toUpperCase() }} · Thread {{ request.workflow_run.graph_thread_id }}
        </p>
      </section>

      <section
        v-if="request.audit_events?.length"
        class="audit-section"
      >
        <div class="panel-heading">
          <div>
            <p class="overline">
              IMMUTABLE TRACE
            </p><h2>审计记录</h2>
          </div><span>{{ request.audit_events.length }} 条</span>
        </div>
        <ol class="audit-timeline">
          <li
            v-for="event in request.audit_events"
            :key="event.id"
          >
            <span class="audit-dot" />
            <div><strong>{{ event.action }}</strong><small>{{ new Date(event.created_at).toLocaleString("zh-CN", { hour12: false }) }} · Request {{ event.request_id.slice(0, 8).toUpperCase() }}</small></div>
          </li>
        </ol>
      </section>
    </template>

    <Teleport to="body">
      <div
        v-if="fulfillmentDialogOpen && nextFulfillmentStatus"
        class="dialog-backdrop"
        role="presentation"
        @click.self="!fulfilling && (fulfillmentDialogOpen = false)"
      >
        <section
          class="submit-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="fulfillment-dialog-title"
        >
          <p class="overline">
            DEMO FULFILLMENT
          </p>
          <h2 id="fulfillment-dialog-title">
            {{ fulfillmentLabels[nextFulfillmentStatus] }}
          </h2>
          <p>此操作只更新本地演示状态并写入审计记录，不会执行真实下单、收货或付款。</p>
          <label class="dialog-note">
            <span>履约备注（可选）</span>
            <textarea
              v-model="fulfillmentNote"
              rows="3"
              maxlength="500"
            />
          </label>
          <div class="dialog-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="fulfilling"
              @click="fulfillmentDialogOpen = false"
            >
              返回检查
            </button>
            <button
              class="primary-button"
              type="button"
              :disabled="fulfilling"
              @click="advanceFulfillment"
            >
              <PackageCheck :size="16" />{{ fulfilling ? "处理中" : "确认模拟操作" }}
            </button>
          </div>
        </section>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="submitDialogOpen && approvalPreview"
        class="dialog-backdrop"
        role="presentation"
        @click.self="!submitting && (submitDialogOpen = false)"
      >
        <section
          class="submit-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="submit-dialog-title"
        >
          <p class="overline">
            APPROVAL PREVIEW
          </p>
          <h2 id="submit-dialog-title">
            确认提交审批
          </h2>
          <p>总预算 <strong><MoneyDisplay :value="approvalPreview.total_budget" /></strong>，提交后草稿内容和候选方案将锁定。</p>
          <ol class="preview-chain">
            <li
              v-for="stage in approvalPreview.stages"
              :key="stage.stage"
            >
              <span class="stage-index">{{ stage.stage }}</span>
              <span><strong>{{ stage.assignee_username }}</strong><small>{{ stage.assignee_department }} · {{ stage.approver_role }}</small></span>
            </li>
          </ol>
          <div class="dialog-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="submitting"
              @click="submitDialogOpen = false"
            >
              返回检查
            </button>
            <button
              class="primary-button"
              type="button"
              :disabled="submitting"
              @click="submitForApproval"
            >
              <Send :size="16" />{{ submitting ? "提交中" : "确认提交" }}
            </button>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>
