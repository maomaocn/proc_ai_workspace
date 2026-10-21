<script setup lang="ts">
import { Boxes, Pencil, Plus, X } from "@lucide/vue"
import { computed, onMounted, reactive, ref } from "vue"

import { api, ApiError } from "../api/client"
import type { InventoryItem } from "../api/types"
import { auth } from "../auth/store"
import MoneyDisplay from "../components/MoneyDisplay.vue"

const items = ref<InventoryItem[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref("")
const success = ref("")
const editingId = ref("")
const canManage = computed(() => auth.user.value?.roles.includes("ADMIN") ?? false)
const form = reactive({
  sku: "",
  category: "",
  model: "",
  available_qty: 0,
  reference_price: "",
  active: true,
})

function resetForm(): void {
  editingId.value = ""
  Object.assign(form, { sku: "", category: "", model: "", available_qty: 0, reference_price: "", active: true })
}

function edit(item: InventoryItem): void {
  editingId.value = item.id
  Object.assign(form, {
    sku: item.sku,
    category: item.category,
    model: item.model,
    available_qty: item.available_qty,
    reference_price: item.reference_price,
    active: item.active,
  })
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    items.value = (await api.inventoryItems()).items
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取库存"
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!canManage.value || saving.value) return
  saving.value = true
  error.value = ""
  success.value = ""
  try {
    if (editingId.value) {
      await api.updateInventoryItem(editingId.value, {
        category: form.category,
        model: form.model,
        available_qty: form.available_qty,
        reference_price: form.reference_price,
        active: form.active,
      })
      success.value = "库存商品已更新。"
    } else {
      await api.createInventoryItem({ ...form })
      success.value = "库存商品已创建。"
    }
    resetForm()
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "库存保存失败"
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="business-page">
    <header class="business-header">
      <div>
        <p class="overline">
          LOCAL INVENTORY
        </p>
        <h1>库存目录</h1>
        <p>库存数量和参考价格均来自本地 PostgreSQL；员工只读，管理员可维护。</p>
      </div>
      <span class="mock-indicator"><Boxes :size="16" /> DATABASE · DEMO</span>
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

    <section
      v-if="canManage"
      class="maintenance-band"
    >
      <div class="panel-heading">
        <div>
          <p class="overline">
            ADMIN MAINTENANCE
          </p><h2>{{ editingId ? "编辑库存" : "新增库存" }}</h2>
        </div>
        <button
          v-if="editingId"
          class="icon-button bordered"
          type="button"
          title="取消编辑"
          @click="resetForm"
        >
          <X :size="17" />
        </button>
      </div>
      <form
        class="maintenance-form"
        @submit.prevent="submit"
      >
        <label><span>SKU</span><input
          v-model.trim="form.sku"
          :disabled="Boolean(editingId)"
          required
        ></label>
        <label><span>品类</span><input
          v-model.trim="form.category"
          required
        ></label>
        <label><span>型号</span><input
          v-model.trim="form.model"
          required
        ></label>
        <label><span>可用数量</span><input
          v-model.number="form.available_qty"
          type="number"
          min="0"
          required
        ></label>
        <label><span>参考价格</span><input
          v-model="form.reference_price"
          type="number"
          min="0.01"
          step="0.01"
          required
        ></label>
        <label class="toggle-label"><input
          v-model="form.active"
          type="checkbox"
        > 启用</label>
        <button
          class="primary-button"
          type="submit"
          :disabled="saving"
        >
          <Plus
            v-if="!editingId"
            :size="17"
          /><Pencil
            v-else
            :size="17"
          />{{ saving ? "保存中" : editingId ? "保存修改" : "新增商品" }}
        </button>
      </form>
    </section>

    <div
      v-if="loading"
      class="business-state"
    >
      正在加载库存...
    </div>
    <div
      v-else-if="items.length === 0"
      class="business-state"
    >
      <h2>暂无库存商品</h2>
    </div>
    <div
      v-else
      class="table-scroll inventory-table-wrap"
    >
      <table class="business-table">
        <thead>
          <tr>
            <th>SKU / 型号</th><th>品类</th><th>可用数量</th><th>参考价格</th><th>状态</th><th v-if="canManage">
              操作
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.id"
          >
            <td><strong>{{ item.sku }}</strong><small>{{ item.model }}</small></td>
            <td>{{ item.category }}</td>
            <td>{{ item.available_qty }}</td>
            <td><MoneyDisplay :value="item.reference_price" /></td>
            <td><span :class="['status-badge', item.active ? 'success' : 'muted']">{{ item.active ? "启用" : "停用" }}</span></td>
            <td v-if="canManage">
              <button
                class="icon-button bordered"
                type="button"
                title="编辑库存"
                @click="edit(item)"
              >
                <Pencil :size="16" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
