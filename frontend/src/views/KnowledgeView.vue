<script setup lang="ts">
import {
  BookOpenCheck,
  FileSearch,
  FileText,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "@lucide/vue"
import { computed, onMounted, ref, watch } from "vue"

import { ApiError, api } from "../api/client"
import type {
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeSearchResponse,
} from "../api/types"
import { auth } from "../auth/store"
import ConfirmDialog from "../components/ConfirmDialog.vue"
import SourceCitation from "../components/SourceCitation.vue"

const collections = ref<KnowledgeCollection[]>([])
const selectedCollectionId = ref("")
const documents = ref<KnowledgeDocument[]>([])
const selectedFile = ref<File | null>(null)
const query = ref("")
const topK = ref(5)
const result = ref<KnowledgeSearchResponse | null>(null)
const loading = ref(true)
const documentsLoading = ref(false)
const uploading = ref(false)
const searching = ref(false)
const deleting = ref(false)
const error = ref("")
const notice = ref("")
const pendingDelete = ref<KnowledgeDocument | null>(null)

const isAdmin = computed(() => auth.user.value?.roles.includes("ADMIN") ?? false)
const selectedCollection = computed(() =>
  collections.value.find((collection) => collection.id === selectedCollectionId.value),
)

function errorMessage(value: unknown): string {
  return value instanceof ApiError ? value.message : "请求失败，请稍后重试"
}

function statusLabel(status: KnowledgeDocument["status"]): string {
  return {
    PENDING: "等待索引",
    INDEXING: "索引中",
    READY: "可检索",
    FAILED: "索引失败",
    DELETED: "已删除",
  }[status]
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadCollections(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    collections.value = await api.knowledgeCollections()
    if (!collections.value.some((item) => item.id === selectedCollectionId.value)) {
      selectedCollectionId.value = collections.value[0]?.id ?? ""
    }
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    loading.value = false
  }
}

async function loadDocuments(): Promise<void> {
  if (!selectedCollectionId.value) {
    documents.value = []
    return
  }
  documentsLoading.value = true
  error.value = ""
  try {
    documents.value = (await api.knowledgeDocuments(selectedCollectionId.value)).items
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    documentsLoading.value = false
  }
}

function chooseFile(event: Event): void {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
  notice.value = ""
}

async function uploadDocument(): Promise<void> {
  if (!selectedFile.value || !selectedCollectionId.value) return
  uploading.value = true
  error.value = ""
  notice.value = ""
  try {
    const uploaded = await api.uploadKnowledgeDocument(
      selectedCollectionId.value,
      selectedFile.value,
    )
    notice.value = `《${uploaded.filename}》已完成索引，可用于检索。`
    selectedFile.value = null
    await Promise.all([loadDocuments(), loadCollections()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    uploading.value = false
  }
}

async function searchKnowledge(): Promise<void> {
  if (query.value.trim().length < 2 || !selectedCollectionId.value) return
  searching.value = true
  error.value = ""
  result.value = null
  try {
    result.value = await api.searchKnowledge(
      selectedCollectionId.value,
      query.value.trim(),
      topK.value,
    )
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    searching.value = false
  }
}

async function deleteDocument(): Promise<void> {
  if (!pendingDelete.value) return
  deleting.value = true
  error.value = ""
  try {
    const filename = pendingDelete.value.filename
    await api.deleteKnowledgeDocument(pendingDelete.value.id)
    pendingDelete.value = null
    result.value = null
    notice.value = `《${filename}》及对应向量已删除。`
    await Promise.all([loadDocuments(), loadCollections()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    deleting.value = false
  }
}

watch(selectedCollectionId, () => {
  result.value = null
  void loadDocuments()
})

onMounted(loadCollections)
</script>

<template>
  <div class="knowledge-page">
    <header class="knowledge-header">
      <div>
        <p class="section-label">
          ENTERPRISE KNOWLEDGE
        </p>
        <h1>企业知识库</h1>
        <p>检索内部制度时始终显示真实来源；无依据时系统会明确拒答。</p>
      </div>
      <div class="mock-indicator">
        <BookOpenCheck :size="18" />
        Mock Embedding · Chroma
      </div>
    </header>

    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-if="notice"
      class="inline-success"
      role="status"
    >
      {{ notice }}
    </div>

    <section
      v-if="loading"
      class="knowledge-state"
    >
      正在读取授权知识库…
    </section>
    <section
      v-else-if="collections.length === 0"
      class="knowledge-state"
    >
      <BookOpenCheck :size="28" />
      <h2>暂无可访问的知识库</h2>
      <p>请联系管理员为你的用户或角色授予读取权限。</p>
    </section>
    <template v-else>
      <section class="knowledge-toolbar">
        <label>
          <span>当前知识库</span>
          <select v-model="selectedCollectionId">
            <option
              v-for="collection in collections"
              :key="collection.id"
              :value="collection.id"
            >
              {{ collection.name }} · {{ collection.document_count }} 份文档
            </option>
          </select>
        </label>
        <span class="permission-badge">
          {{ selectedCollection?.effective_permission }}
        </span>
        <button
          class="icon-button"
          type="button"
          title="刷新知识库"
          aria-label="刷新知识库"
          :disabled="loading || documentsLoading"
          @click="loadCollections"
        >
          <RefreshCw :size="18" />
        </button>
      </section>

      <div class="knowledge-layout">
        <section class="document-panel">
          <div class="panel-heading">
            <div>
              <p class="section-label">
                DOCUMENTS
              </p>
              <h2>制度文档</h2>
            </div>
            <span>{{ documents.length }} 份</span>
          </div>

          <form
            v-if="isAdmin"
            class="upload-row"
            @submit.prevent="uploadDocument"
          >
            <label class="file-picker">
              <Upload :size="17" />
              <span>{{ selectedFile?.name || "选择 PDF / TXT / MD" }}</span>
              <input
                type="file"
                accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
                @change="chooseFile"
              >
            </label>
            <button
              class="primary-button"
              type="submit"
              :disabled="!selectedFile || uploading"
            >
              {{ uploading ? "解析索引中…" : "上传并索引" }}
            </button>
          </form>

          <p
            v-if="documentsLoading"
            class="panel-placeholder"
          >
            正在读取文档…
          </p>
          <p
            v-else-if="documents.length === 0"
            class="panel-placeholder"
          >
            当前知识库还没有文档。
          </p>
          <div
            v-else
            class="document-list"
          >
            <article
              v-for="document in documents"
              :key="document.id"
              class="document-row"
            >
              <FileText :size="20" />
              <div>
                <RouterLink
                  class="document-name"
                  :to="{ name: 'knowledge-document', params: { documentId: document.id } }"
                >
                  {{ document.filename }}
                </RouterLink>
                <p>
                  {{ formatBytes(document.size_bytes) }} · {{ document.chunk_count }} 个片段 ·
                  {{ document.uploader.username }}
                </p>
                <small v-if="document.error_code">{{ document.error_code }}</small>
              </div>
              <span :class="['document-status', document.status.toLowerCase()]">
                {{ statusLabel(document.status) }}
              </span>
              <button
                v-if="isAdmin"
                class="icon-button danger-icon"
                type="button"
                title="删除文档及向量"
                aria-label="删除文档及向量"
                @click="pendingDelete = document"
              >
                <Trash2 :size="17" />
              </button>
            </article>
          </div>
        </section>

        <section class="search-panel">
          <div class="panel-heading">
            <div>
              <p class="section-label">
                RETRIEVAL TEST
              </p>
              <h2>引用检索</h2>
            </div>
            <FileSearch :size="22" />
          </div>
          <form
            class="knowledge-search-form"
            @submit.prevent="searchKnowledge"
          >
            <label for="knowledge-query">问题</label>
            <textarea
              id="knowledge-query"
              v-model="query"
              rows="3"
              maxlength="1000"
              placeholder="例如：笔记本超过一万元需要几级审批？"
            />
            <div class="top-k-control">
              <label for="top-k">返回片段</label>
              <input
                id="top-k"
                v-model.number="topK"
                type="range"
                min="1"
                max="10"
              >
              <output for="top-k">{{ topK }}</output>
            </div>
            <button
              class="primary-button"
              type="submit"
              :disabled="query.trim().length < 2 || searching"
            >
              <Search :size="17" />
              {{ searching ? "检索中…" : "检索知识库" }}
            </button>
          </form>

          <div
            v-if="result"
            class="search-result"
          >
            <div :class="['answer-box', { empty: !result.has_sufficient_evidence }]">
              <span>{{ result.source }} 检索</span>
              <p>{{ result.answer }}</p>
            </div>
            <div
              v-if="result.hits.length"
              class="citation-list"
            >
              <SourceCitation
                v-for="hit in result.hits"
                :key="hit.chunk_id"
                :hit="hit"
              />
            </div>
          </div>
        </section>
      </div>
    </template>

    <ConfirmDialog
      :open="Boolean(pendingDelete)"
      title="删除知识文档"
      :description="`删除《${pendingDelete?.filename || ''}》后，对应向量会同步移除，后续检索将立即不可见。`"
      confirm-label="删除文档"
      :busy="deleting"
      @cancel="pendingDelete = null"
      @confirm="deleteDocument"
    />
  </div>
</template>
