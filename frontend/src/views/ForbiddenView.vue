<script setup lang="ts">
import { ShieldX } from "@lucide/vue"
</script>

<template>
  <main class="access-state-page">
    <ShieldX :size="36" />
    <p class="overline">
      403 · FORBIDDEN
    </p>
    <h1>当前账号没有访问权限</h1>
    <p>页面权限由后端角色策略决定。请返回工作台选择可访问的业务模块。</p>
    <RouterLink
      class="primary-button"
      to="/"
    >
      返回工作台
    </RouterLink>
  </main>
</template>
