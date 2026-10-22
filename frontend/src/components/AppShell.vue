<script setup lang="ts">
import {
  BookOpen,
  Boxes,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  MessageSquareText,
  Store,
  X,
} from "@lucide/vue"
import { computed, ref } from "vue"
import { useRouter } from "vue-router"

import { auth } from "../auth/store"

const router = useRouter()
const navigationOpen = ref(false)
const canManageSuppliers = computed(() => auth.user.value?.roles.some(
  role => role === "PROCUREMENT" || role === "ADMIN",
))
const canApprove = computed(() => auth.user.value?.roles.includes("APPROVER"))
const canAdminister = computed(() => auth.user.value?.roles.includes("ADMIN"))

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
        <RouterLink
          to="/knowledge"
          @click="navigationOpen = false"
        >
          <BookOpen :size="18" />
          企业知识库
        </RouterLink>
        <RouterLink
          to="/procurements"
          @click="navigationOpen = false"
        >
          <FileText :size="18" />
          采购申请
        </RouterLink>
        <RouterLink
          to="/inventory"
          @click="navigationOpen = false"
        >
          <Boxes :size="18" />
          库存目录
        </RouterLink>
        <RouterLink
          v-if="canApprove"
          to="/approvals"
          @click="navigationOpen = false"
        >
          <ClipboardCheck :size="18" />
          我的审批
        </RouterLink>
        <RouterLink
          v-if="canManageSuppliers"
          to="/suppliers"
          @click="navigationOpen = false"
        >
          <Store :size="18" />
          供应商报价
        </RouterLink>
        <RouterLink
          v-if="canAdminister"
          to="/admin/approval-rules"
          @click="navigationOpen = false"
        >
          <ListChecks :size="18" />
          审批规则
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
