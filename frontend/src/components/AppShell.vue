<script setup lang="ts">
import { LayoutDashboard, LogOut, Menu, MessageSquareText, X } from "@lucide/vue"
import { ref } from "vue"
import { useRouter } from "vue-router"

import { auth } from "../auth/store"

const router = useRouter()
const navigationOpen = ref(false)

async function signOut(): Promise<void> {
  auth.logout()
  await router.replace({ name: "login" })
}
</script>

<template>
  <div class="app-frame">
    <header class="mobile-header">
      <RouterLink
        class="mobile-brand"
        to="/"
      >
        <span class="brand-symbol">EA</span>
        <strong>Agent Hub</strong>
      </RouterLink>
      <button
        class="icon-button"
        type="button"
        :aria-label="navigationOpen ? '关闭导航' : '打开导航'"
        @click="navigationOpen = !navigationOpen"
      >
        <X
          v-if="navigationOpen"
          :size="20"
        />
        <Menu
          v-else
          :size="20"
        />
      </button>
    </header>

    <aside :class="['sidebar', { open: navigationOpen }]">
      <RouterLink
        class="brand"
        to="/"
        @click="navigationOpen = false"
      >
        <span class="brand-symbol">EA</span>
        <span>
          <small>ENTERPRISE OPERATIONS</small>
          <strong>Agent Hub</strong>
        </span>
      </RouterLink>

      <nav aria-label="主导航">
        <RouterLink
          to="/"
          @click="navigationOpen = false"
        >
          <LayoutDashboard :size="18" />
          工作台
        </RouterLink>
        <RouterLink
          to="/assistant"
          @click="navigationOpen = false"
        >
          <MessageSquareText :size="18" />
          AI 采购助手
        </RouterLink>
      </nav>

      <div class="sidebar-account">
        <span class="avatar">{{ auth.user.value?.username.slice(0, 1).toUpperCase() }}</span>
        <span class="account-copy">
          <strong>{{ auth.user.value?.username }}</strong>
          <small>{{ auth.user.value?.department.name }}</small>
        </span>
        <button
          class="icon-button"
          type="button"
          title="退出登录"
          aria-label="退出登录"
          @click="signOut"
        >
          <LogOut :size="18" />
        </button>
      </div>
    </aside>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
