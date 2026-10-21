<script setup lang="ts">
import { BadgeDollarSign, Plus, Power } from "@lucide/vue"
import { onMounted, reactive, ref } from "vue"

import { api, ApiError } from "../api/client"
import type { InventoryItem, Supplier, SupplierQuote } from "../api/types"
import MoneyDisplay from "../components/MoneyDisplay.vue"

const suppliers = ref<Supplier[]>([])
const quotes = ref<SupplierQuote[]>([])
const inventory = ref<InventoryItem[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref("")
const success = ref("")
const supplierForm = reactive({ name: "", active: true })
const quoteForm = reactive({ supplier_id: "", inventory_item_id: "", unit_price: "", quoted_at: new Date().toISOString().slice(0, 16) })

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    const [supplierPage, quotePage, inventoryPage] = await Promise.all([
      api.suppliers(),
      api.supplierQuotes(),
      api.inventoryItems(),
    ])
    suppliers.value = supplierPage.items
    quotes.value = quotePage.items
    inventory.value = inventoryPage.items.filter(item => item.active)
    if (!quoteForm.supplier_id && suppliers.value[0]) quoteForm.supplier_id = suppliers.value[0].id
    if (!quoteForm.inventory_item_id && inventory.value[0]) quoteForm.inventory_item_id = inventory.value[0].id
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取供应商数据"
  } finally {
    loading.value = false
  }
}

async function createSupplier(): Promise<void> {
  if (!supplierForm.name.trim() || saving.value) return
  saving.value = true
  error.value = ""
  try {
    await api.createSupplier({ ...supplierForm })
    supplierForm.name = ""
    success.value = "演示供应商已创建。"
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "供应商创建失败"
  } finally {
    saving.value = false
  }
}

async function toggleSupplier(item: Supplier): Promise<void> {
  try {
    await api.updateSupplier(item.id, { active: !item.active })
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "供应商状态更新失败"
  }
}

async function createQuote(): Promise<void> {
  if (!quoteForm.supplier_id || !quoteForm.inventory_item_id || !quoteForm.unit_price || saving.value) return
  saving.value = true
  error.value = ""
  try {
    await api.createSupplierQuote({
      supplier_id: quoteForm.supplier_id,
      inventory_item_id: quoteForm.inventory_item_id,
      unit_price: quoteForm.unit_price,
      quoted_at: new Date(quoteForm.quoted_at).toISOString(),
    })
    quoteForm.unit_price = ""
    quoteForm.quoted_at = new Date().toISOString().slice(0, 16)
    success.value = "DEMO 报价已创建。"
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "报价创建失败"
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
          SUPPLIERS & QUOTES
        </p><h1>供应商与报价</h1><p>所有供应商和报价均为本地演示数据，不代表实时市场价格。</p>
      </div>
      <span class="mock-indicator"><BadgeDollarSign :size="16" /> LOCAL DEMO DATA</span>
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
    <div
      v-if="loading"
      class="business-state"
    >
      正在加载供应商与报价...
    </div>
    <template v-else>
      <div class="supplier-layout">
        <section>
          <div class="panel-heading">
            <div>
              <p class="overline">
                SUPPLIERS
              </p><h2>供应商</h2>
            </div><span>{{ suppliers.length }} 家</span>
          </div>
          <form
            class="inline-create-form"
            @submit.prevent="createSupplier"
          >
            <label><span>供应商名称</span><input
              v-model.trim="supplierForm.name"
              placeholder="仅用于本地演示"
              required
            ></label>
            <button
              class="primary-button"
              type="submit"
              :disabled="saving"
            >
              <Plus :size="16" />新增
            </button>
          </form>
          <div class="supplier-list">
            <div
              v-for="item in suppliers"
              :key="item.id"
            >
              <span><strong>{{ item.name }}</strong><small>DEMO DATA</small></span>
              <span :class="['status-badge', item.active ? 'success' : 'muted']">{{ item.active ? "启用" : "停用" }}</span>
              <button
                class="icon-button bordered"
                type="button"
                :title="item.active ? '停用供应商' : '启用供应商'"
                @click="toggleSupplier(item)"
              >
                <Power :size="16" />
              </button>
            </div>
          </div>
        </section>
        <section>
          <div class="panel-heading">
            <div>
              <p class="overline">
                NEW QUOTE
              </p><h2>新增报价</h2>
            </div><span class="demo-badge">DEMO</span>
          </div>
          <form
            class="business-form quote-form"
            @submit.prevent="createQuote"
          >
            <label><span>供应商</span><select
              v-model="quoteForm.supplier_id"
              required
            ><option
              v-for="item in suppliers.filter(row => row.active)"
              :key="item.id"
              :value="item.id"
            >{{ item.name }}</option></select></label>
            <label><span>库存商品</span><select
              v-model="quoteForm.inventory_item_id"
              required
            ><option
              v-for="item in inventory"
              :key="item.id"
              :value="item.id"
            >{{ item.sku }} · {{ item.model }}</option></select></label>
            <label><span>含税单价（元）</span><input
              v-model="quoteForm.unit_price"
              type="number"
              min="0.01"
              step="0.01"
              required
            ></label>
            <label><span>报价时间</span><input
              v-model="quoteForm.quoted_at"
              type="datetime-local"
              required
            ></label>
            <div class="form-actions wide-field">
              <button
                class="primary-button"
                type="submit"
                :disabled="saving"
              >
                <Plus :size="16" />{{ saving ? "保存中" : "保存 DEMO 报价" }}
              </button>
            </div>
          </form>
        </section>
      </div>
      <section class="quote-history">
        <div class="panel-heading">
          <div>
            <p class="overline">
              QUOTE HISTORY
            </p><h2>报价记录</h2>
          </div><span>{{ quotes.length }} 条</span>
        </div>
        <div
          v-if="quotes.length === 0"
          class="business-state compact"
        >
          暂无报价。
        </div>
        <div
          v-else
          class="table-scroll"
        >
          <table class="business-table">
            <thead><tr><th>商品</th><th>供应商</th><th>单价</th><th>来源</th><th>报价时间</th></tr></thead><tbody>
              <tr
                v-for="quote in quotes"
                :key="quote.id"
              >
                <td><strong>{{ quote.inventory_item.sku }}</strong><small>{{ quote.inventory_item.model }}</small></td><td>{{ quote.supplier.name }}</td><td><MoneyDisplay :value="quote.unit_price" /></td><td><span class="demo-badge">{{ quote.source_type }}</span></td><td>{{ new Date(quote.quoted_at).toLocaleString("zh-CN", { hour12: false }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
