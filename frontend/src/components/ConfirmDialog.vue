<script setup lang="ts">
import { AlertTriangle, X } from "@lucide/vue"

defineProps<{
  open: boolean
  title: string
  description: string
  confirmLabel: string
  busy?: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="dialog-backdrop"
      role="presentation"
      @click.self="emit('cancel')"
    >
      <section
        class="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        :aria-labelledby="`${title}-title`"
      >
        <button
          class="icon-button dialog-close"
          type="button"
          title="关闭"
          aria-label="关闭"
          :disabled="busy"
          @click="emit('cancel')"
        >
          <X :size="18" />
        </button>
        <AlertTriangle
          class="dialog-warning"
          :size="26"
        />
        <h2 :id="`${title}-title`">
          {{ title }}
        </h2>
        <p>{{ description }}</p>
        <div class="dialog-actions">
          <button
            class="secondary-button"
            type="button"
            :disabled="busy"
            @click="emit('cancel')"
          >
            取消
          </button>
          <button
            class="danger-button"
            type="button"
            :disabled="busy"
            @click="emit('confirm')"
          >
            {{ busy ? "处理中…" : confirmLabel }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
