<script setup lang="ts">
import { ArrowLeft, RefreshCw, Save, Sparkles } from "@lucide/vue"
import { computed, onMounted, reactive, ref } from "vue"
import { useRoute } from "vue-router"

import { api, ApiError } from "../api/client"
import type { Procurement, ProcurementPlan } from "../api/types"
import { auth } from "../auth/store"
import MoneyDisplay from "../components/MoneyDisplay.vue"
import SourceCitation from "../components/SourceCitation.vue"

const route = useRoute()
const request = ref<Procurement | null>(null)
const plan = ref<ProcurementPlan | null>(null)
const loading = ref(true)
const saving = ref(false)
const planning = ref(false)
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
        <span :class="['status-badge', request.status.toLowerCase()]">{{ request.status === "DRAFT" ? "草稿" : request.status }}</span>
      </header>

      <section class="procurement-summary-band">
        <div><span>数量</span><strong>{{ request.quantity }}</strong></div>
        <div><span>单价上限</span><strong><MoneyDisplay :value="request.unit_price_limit" /></strong></div>
        <div><span>服务端总预算</span><strong><MoneyDisplay :value="request.total_budget" /></strong></div>
        <div><span>候选方案</span><strong>{{ request.candidates?.length || 0 }}</strong></div>
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
          <small v-if="!canEdit">只有申请人可为草稿生成方案；提交审批将在 M4 实现。</small>
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
    </template>
  </div>
</template>
