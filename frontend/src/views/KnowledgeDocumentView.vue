<script setup lang="ts">
import { ArrowLeft, FileText, RefreshCw } from "@lucide/vue"
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { ApiError, api } from "../api/client"
import type { KnowledgeDocumentDetail } from "../api/types"
import { auth } from "../auth/store"

const route = useRoute()
const document = ref<KnowledgeDocumentDetail | null>(null)
const loading = ref(true)
const reindexing = ref(false)
const error = ref("")
const isAdmin = computed(() => auth.user.value?.roles.includes("ADMIN") ?? false)

function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadDocument(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    document.value = await api.knowledgeDocument(String(route.params.documentId))
  } catch (value) {
    error.value = value instanceof ApiError ? value.message : "文档读取失败"
  } finally {
    loading.value = false
  }
}

async function reindex(): Promise<void> {
  if (!document.value) return
  reindexing.value = true
  error.value = ""
  try {
    await api.reindexKnowledgeDocument(document.value.id)
    await loadDocument()
  } catch (value) {
    error.value = value instanceof ApiError ? value.message : "重建索引失败"
  } finally {
    reindexing.value = false
  }
}

onMounted(loadDocument)
</script>

<template>
  <div class="document-detail-page">
    <RouterLink
      class="back-link"
      to="/knowledge"
    >
      <ArrowLeft :size="17" />
      返回知识库
    </RouterLink>

    <p
      v-if="loading"
      class="knowledge-state"
    >
      正在读取文档…
    </p>
    <div
      v-else-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <template v-else-if="document">
      <header class="document-detail-header">
        <div class="document-detail-icon">
          <FileText :size="24" />
        </div>
        <div>
          <p class="section-label">
            KNOWLEDGE DOCUMENT
          </p>
          <h1>{{ document.filename }}</h1>
          <p>
            {{ formatBytes(document.size_bytes) }} · {{ document.mime_type }} · 索引版本
            {{ document.index_version }}
          </p>
        </div>
        <span :class="['document-status', document.status.toLowerCase()]">
          {{ document.status }}
        </span>
        <button
          v-if="isAdmin"
          class="secondary-button"
          type="button"
          :disabled="reindexing"
          @click="reindex"
        >
          <RefreshCw :size="17" />
          {{ reindexing ? "重建中…" : "重建索引" }}
        </button>
      </header>

      <section class="document-metadata">
        <div><span>上传者</span><strong>{{ document.uploader.username }}</strong></div>
        <div><span>分块数量</span><strong>{{ document.chunk_count }}</strong></div>
        <div><span>SHA-256</span><code>{{ document.sha256 }}</code></div>
        <div><span>最近更新</span><strong>{{ new Date(document.updated_at).toLocaleString() }}</strong></div>
      </section>

      <section class="chunk-section">
        <div class="panel-heading">
          <div>
            <p class="section-label">
              INDEXED CHUNKS
            </p>
            <h2>可见片段</h2>
          </div>
          <span>{{ document.chunks.length }} 个</span>
        </div>
        <p
          v-if="document.chunks.length === 0"
          class="panel-placeholder"
        >
          暂无已索引片段。
        </p>
        <article
          v-for="chunk in document.chunks"
          :key="chunk.id"
          class="chunk-row"
        >
          <div>
            <span>#{{ chunk.chunk_index + 1 }}</span>
            <span>{{ chunk.page_number ? `第 ${chunk.page_number} 页` : "页码不可用" }}</span>
          </div>
          <p>{{ chunk.content }}</p>
        </article>
      </section>
    </template>
  </div>
</template>
