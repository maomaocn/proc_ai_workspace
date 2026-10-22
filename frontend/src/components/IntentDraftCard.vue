<script setup lang="ts">
import { Check, FileCheck2 } from "@lucide/vue"
import { computed, reactive, ref, watch } from "vue"

import type { ChatMessage, PurchaseIntent } from "../api/types"

const props = defineProps<{
  message: ChatMessage
  busy?: boolean
}>()
const emit = defineEmits<{
  confirm: [intent: PurchaseIntent]
}>()

const submitted = ref(false)

function sourceIntent(): PurchaseIntent {
  const payload = props.message.payload_json
  const intent = payload?.confirmed_intent || payload?.intent || {
    category: null,
    item_description: null,
    quantity: null,
    unit_price_limit: null,
    total_budget: null,
    purpose: null,
    priority: "NORMAL",
    notes: null,
  }
  return { ...intent }
}

const draft = reactive<PurchaseIntent>(sourceIntent())
watch(() => props.message, () => Object.assign(draft, sourceIntent()))

function syncTotalBudget(): void {
  const quantity = Number(draft.quantity)
  const unitPrice = Number(draft.unit_price_limit)
  draft.total_budget = quantity > 0 && unitPrice > 0
    ? (quantity * unitPrice).toFixed(2)
    : null
}

watch([() => draft.quantity, () => draft.unit_price_limit], syncTotalBudget)

const requiredComplete = computed(() => Boolean(
  draft.category && draft.quantity && draft.quantity > 0 && draft.unit_price_limit && draft.purpose,
))
const isConfirmed = computed(() => props.message.status === "CONFIRMED")

function submit(): void {
  submitted.value = true
  if (!requiredComplete.value || isConfirmed.value) return
  syncTotalBudget()
  emit("confirm", {
    ...draft,
    unit_price_limit: Number(draft.unit_price_limit).toFixed(2),
  })
}
</script>

<template>
  <section
    class="intent-card"
    aria-label="结构化采购意图"
  >
    <header class="intent-card-header">
      <div>
        <p class="overline">
          STRUCTURED INTENT
        </p>
        <h3>采购需求草稿</h3>
      </div>
      <span :class="['status-badge', isConfirmed ? 'success' : 'pending']">
        <Check
          v-if="isConfirmed"
          :size="14"
        />
        {{ isConfirmed ? "已确认" : "待确认" }}
      </span>
    </header>

    <form
      class="intent-form"
      @submit.prevent="submit"
    >
      <label>
        <span>采购品类 *</span>
        <input
          v-model.trim="draft.category"
          :disabled="isConfirmed"
          placeholder="例如：笔记本电脑"
        >
        <small
          v-if="submitted && !draft.category"
          class="field-error"
        >请填写采购品类</small>
      </label>
      <label>
        <span>商品描述</span>
        <input
          v-model.trim="draft.item_description"
          :disabled="isConfirmed"
          placeholder="型号或配置偏好"
        >
      </label>
      <label>
        <span>数量 *</span>
        <input
          v-model.number="draft.quantity"
          :disabled="isConfirmed"
          min="1"
          type="number"
        >
        <small
          v-if="submitted && (!draft.quantity || draft.quantity < 1)"
          class="field-error"
        >数量必须大于 0</small>
      </label>
      <label>
        <span>单价上限（元）*</span>
        <input
          v-model="draft.unit_price_limit"
          :disabled="isConfirmed"
          min="0.01"
          step="0.01"
          type="number"
        >
        <small
          v-if="submitted && !draft.unit_price_limit"
          class="field-error"
        >请填写单价预算</small>
      </label>
      <label>
        <span>总预算（元）</span>
        <input
          v-model="draft.total_budget"
          :disabled="isConfirmed"
          aria-readonly="true"
          min="0.01"
          readonly
          step="0.01"
          type="number"
        >
      </label>
      <label>
        <span>优先级</span>
        <select
          v-model="draft.priority"
          :disabled="isConfirmed"
        >
          <option value="LOW">低</option>
          <option value="NORMAL">普通</option>
          <option value="HIGH">高</option>
        </select>
      </label>
      <label class="wide-field">
        <span>采购用途 *</span>
        <textarea
          v-model.trim="draft.purpose"
          :disabled="isConfirmed"
          rows="2"
          placeholder="说明使用部门和业务用途"
        />
        <small
          v-if="submitted && !draft.purpose"
          class="field-error"
        >请填写采购用途</small>
      </label>
      <label class="wide-field">
        <span>备注</span>
        <textarea
          v-model.trim="draft.notes"
          :disabled="isConfirmed"
          rows="2"
          placeholder="其他约束或偏好"
        />
      </label>

      <div class="intent-actions wide-field">
        <p
          v-if="isConfirmed"
          class="confirmation-note"
        >
          <FileCheck2 :size="17" />
          已创建采购草稿，尚未提交审批。
          <RouterLink
            v-if="message.payload_json?.purchase_request_id"
            :to="`/procurements/${message.payload_json.purchase_request_id}`"
          >
            查看草稿
          </RouterLink>
        </p>
        <button
          v-else
          class="primary-button"
          type="submit"
          :disabled="busy"
        >
          <Check :size="17" />
          {{ busy ? "正在确认" : "确认需求" }}
        </button>
      </div>
    </form>
  </section>
</template>
