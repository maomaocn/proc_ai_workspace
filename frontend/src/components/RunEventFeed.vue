<script setup lang="ts">
import { Activity, CheckCircle2, CircleAlert, Clock3, Wrench } from "@lucide/vue"
import { computed } from "vue"

import type { AgentEvent } from "../api/types"

const props = defineProps<{ events: AgentEvent[] }>()

const orderedEvents = computed(() => {
  const bySequence = new Map<number, AgentEvent>()
  for (const event of props.events) bySequence.set(event.data.seq, event)
  return [...bySequence.values()].sort((left, right) => left.data.seq - right.data.seq)
})

function label(event: AgentEvent): string {
  if (event.event === "run.started") return "运行已启动"
  if (event.event === "message.delta") return "回复已接收"
  if (event.event === "node.started") return `节点 ${event.data.node || "未知"} 开始`
  if (event.event === "node.completed") return `节点 ${event.data.node || "未知"} 完成`
  if (event.event === "tool.started") return `工具 ${event.data.tool_name || "未知"} 开始`
  if (event.event === "tool.completed") return `工具 ${event.data.tool_name || "未知"} 完成`
  if (event.event === "run.waiting_approval") return "等待人工审批"
  if (event.event === "run.completed") return "运行已完成"
  if (event.event === "run.failed") return `运行失败 · ${event.data.error_code || "UNKNOWN"}`
  return "事件连接正常"
}
</script>

<template>
  <section
    v-if="orderedEvents.length"
    class="run-event-feed"
    aria-label="Agent 运行事件"
  >
    <div class="run-event-heading">
      <Activity :size="15" />
      <strong>运行事件</strong>
      <span>{{ orderedEvents.length }}</span>
    </div>
    <ol>
      <li
        v-for="event in orderedEvents"
        :key="event.data.seq"
      >
        <Wrench
          v-if="event.event.startsWith('tool.')"
          :size="14"
        />
        <Clock3
          v-else-if="event.event === 'run.waiting_approval'"
          :size="14"
        />
        <CircleAlert
          v-else-if="event.event === 'run.failed'"
          :size="14"
        />
        <CheckCircle2
          v-else
          :size="14"
        />
        <span>{{ label(event) }}</span>
        <small>#{{ event.data.seq }}</small>
      </li>
    </ol>
  </section>
</template>
