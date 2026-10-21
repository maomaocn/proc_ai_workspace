<script setup lang="ts">
import { FileText } from "@lucide/vue"

import type { SearchHit } from "../api/types"

defineProps<{ hit: SearchHit }>()
</script>

<template>
  <article class="citation-item">
    <div class="citation-heading">
      <FileText :size="17" />
      <strong>{{ hit.filename }}</strong>
      <span>{{ hit.page_number ? `第 ${hit.page_number} 页` : "页码不可用" }}</span>
      <span class="score">{{ (hit.score * 100).toFixed(1) }}%</span>
    </div>
    <p>{{ hit.snippet }}</p>
    <RouterLink :to="{ name: 'knowledge-document', params: { documentId: hit.document_id } }">
      查看原始片段
    </RouterLink>
  </article>
</template>
