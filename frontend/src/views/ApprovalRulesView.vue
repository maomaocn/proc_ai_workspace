<script setup lang="ts">
import { Plus, Power } from "@lucide/vue"
import { onMounted, reactive, ref } from "vue"

import { api, ApiError } from "../api/client"
import type { ApprovalRule } from "../api/types"
import MoneyDisplay from "../components/MoneyDisplay.vue"

const rules = ref<ApprovalRule[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref("")
const success = ref("")
const form = reactive({ min_amount: "", max_amount: "", stage: 1 })

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    rules.value = await api.approvalRules()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取审批规则"
  } finally {
    loading.value = false
  }
}

async function createRule(): Promise<void> {
  saving.value = true
  error.value = ""
  success.value = ""
  try {
    await api.createApprovalRule({
      min_amount: form.min_amount,
      max_amount: form.max_amount.trim() || null,
      stage: form.stage,
      approver_role: "APPROVER",
      active: true,
    })
    form.min_amount = ""
    form.max_amount = ""
    form.stage = 1
    success.value = "审批规则已新增。"
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "审批规则新增失败"
  } finally {
    saving.value = false
  }
}

async function toggle(rule: ApprovalRule): Promise<void> {
  error.value = ""
  success.value = ""
  try {
    await api.updateApprovalRule(rule.id, { active: !rule.active })
    success.value = rule.active ? "审批规则已停用。" : "审批规则已启用。"
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "审批规则更新失败"
  }
}

onMounted(load)
</script>

<template>
  <div class="business-page approval-rules-page">
    <header class="business-header">
      <div>
        <p class="overline">
          DETERMINISTIC POLICY
        </p><h1>审批规则</h1><p>规则按金额区间与级别确定审批链；有效区间不可重叠。</p>
      </div><span class="source-chip">SERVER RULES</span>
    </header>
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

    <section class="rule-create-band">
      <div>
        <p class="overline">
          NEW RULE
        </p><h2>新增金额规则</h2>
      </div>
      <form
        class="rule-form"
        @submit.prevent="createRule"
      >
        <label><span>最低金额</span><input
          v-model="form.min_amount"
          type="number"
          min="0"
          step="0.01"
          required
        ></label>
        <label><span>最高金额</span><input
          v-model="form.max_amount"
          type="number"
          min="0.01"
          step="0.01"
          placeholder="留空表示无上限"
        ></label>
        <label><span>审批级别</span><input
          v-model.number="form.stage"
          type="number"
          min="1"
          max="20"
          required
        ></label>
        <button
          class="primary-button"
          type="submit"
          :disabled="saving"
        >
          <Plus :size="17" />{{ saving ? "保存中" : "新增规则" }}
        </button>
      </form>
    </section>

    <div
      v-if="loading"
      class="business-state"
    >
      正在读取审批规则...
    </div>
    <div
      v-else
      class="business-table-wrap"
    >
      <table class="business-table">
        <thead><tr><th>金额区间</th><th>级别</th><th>审批角色</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr
            v-for="rule in rules"
            :key="rule.id"
          >
            <td>
              <MoneyDisplay :value="rule.min_amount" /> – <MoneyDisplay
                v-if="rule.max_amount"
                :value="rule.max_amount"
              /><span v-else>无上限</span>
            </td>
            <td>第 {{ rule.stage }} 级</td><td>{{ rule.approver_role }}</td>
            <td><span :class="['status-badge', rule.active ? 'approved' : 'cancelled']">{{ rule.active ? "启用" : "停用" }}</span></td>
            <td>
              <button
                class="icon-button"
                type="button"
                :title="rule.active ? '停用规则' : '启用规则'"
                :aria-label="rule.active ? '停用规则' : '启用规则'"
                @click="toggle(rule)"
              >
                <Power :size="17" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
