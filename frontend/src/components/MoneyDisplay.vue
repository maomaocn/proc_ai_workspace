<script setup lang="ts">
import { computed } from "vue"

const props = withDefaults(defineProps<{
  value: string
  currency?: "CNY"
}>(), {
  currency: "CNY",
})

const formatted = computed(() => new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: props.currency,
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(Number(props.value)))
</script>

<template>
  <span class="money-display">{{ formatted }}</span>
</template>
