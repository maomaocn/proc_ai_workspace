<script setup lang="ts">
import { ArrowLeft, Save } from "@lucide/vue"
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"

import { api, ApiError } from "../api/client"

const router = useRouter()
const saving = ref(false)
const submitted = ref(false)
const error = ref("")
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

async function submit(): Promise<void> {
  submitted.value = true
  if (!form.title.trim() || !form.category.trim() || !form.item_description.trim()
    || !form.purpose.trim() || form.quantity < 1 || Number(form.unit_price_limit) <= 0) return
  saving.value = true
  error.value = ""
  try {
    const created = await api.createProcurement({
      ...form,
      notes: form.notes.trim() || null,
    })
    await router.replace(`/procurements/${created.id}`)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "采购草稿创建失败"
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="business-page narrow-business-page">
    <RouterLink
      class="back-link"
      to="/procurements"
    >
      <ArrowLeft :size="16" />
      返回采购列表
    </RouterLink>
    <header class="business-header compact">
      <div>
        <p class="overline">
          NEW DRAFT
        </p>
        <h1>新建采购草稿</h1>
        <p>总预算由服务端使用 Decimal 按“数量 × 单价上限”计算。</p>
      </div>
    </header>
    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <form
      class="business-form"
      @submit.prevent="submit"
    >
      <label>
        <span>标题 *</span>
        <input
          v-model.trim="form.title"
          placeholder="例如：研发设备采购"
        >
        <small
          v-if="submitted && !form.title"
          class="field-error"
        >请填写标题</small>
      </label>
      <label>
        <span>品类 *</span>
        <input
          v-model.trim="form.category"
          placeholder="例如：笔记本电脑"
        >
        <small
          v-if="submitted && !form.category"
          class="field-error"
        >请填写品类</small>
      </label>
      <label class="wide-field">
        <span>商品描述 *</span>
        <input
          v-model.trim="form.item_description"
          placeholder="型号、配置或规格要求"
        >
      </label>
      <label>
        <span>数量 *</span>
        <input
          v-model.number="form.quantity"
          type="number"
          min="1"
        >
      </label>
      <label>
        <span>单价上限（元）*</span>
        <input
          v-model="form.unit_price_limit"
          type="number"
          min="0.01"
          step="0.01"
        >
      </label>
      <label>
        <span>优先级</span>
        <select v-model="form.priority">
          <option value="LOW">低</option>
          <option value="NORMAL">普通</option>
          <option value="HIGH">高</option>
        </select>
      </label>
      <label class="wide-field">
        <span>用途 *</span>
        <textarea
          v-model.trim="form.purpose"
          rows="3"
          placeholder="说明业务用途和使用部门"
        />
      </label>
      <label class="wide-field">
        <span>备注</span>
        <textarea
          v-model="form.notes"
          rows="3"
          placeholder="其他限制或偏好"
        />
      </label>
      <div class="form-actions wide-field">
        <button
          class="primary-button"
          type="submit"
          :disabled="saving"
        >
          <Save :size="17" />
          {{ saving ? "正在保存" : "保存草稿" }}
        </button>
      </div>
    </form>
  </div>
</template>
