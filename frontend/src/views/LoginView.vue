<script setup lang="ts">
import { ArrowRight, LockKeyhole } from "@lucide/vue"
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { ApiError } from "../api/client"
import { auth } from "../auth/store"

const username = ref("")
const password = ref("")
const error = ref("")
const route = useRoute()
const router = useRouter()

async function submit(): Promise<void> {
  error.value = ""
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === "string" && route.query.redirect.startsWith("/")
      && !route.query.redirect.startsWith("//")
      ? route.query.redirect
      : "/"
    await router.replace(redirect)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "暂时无法登录，请稍后重试"
  }
}
</script>

<template>
  <main class="login-page">
    <section
      class="login-brand-panel"
      aria-label="Enterprise AI Agent Hub"
    >
      <div class="login-brand">
        <span class="brand-symbol large">EA</span>
        <span>
          <small>ENTERPRISE OPERATIONS</small>
          <strong>Enterprise AI Agent Hub</strong>
        </span>
      </div>
      <div class="login-statement">
        <p class="overline">
          SECURE WORKSPACE
        </p>
        <h1>让采购需求从一句话开始。</h1>
        <p>使用企业身份进入工作台，AI 只整理需求，业务确认始终由你完成。</p>
      </div>
      <p class="environment-label">
        M3 · PROCUREMENT & TOOLS
      </p>
    </section>

    <section class="login-form-panel">
      <form
        class="login-form"
        @submit.prevent="submit"
      >
        <div class="form-heading">
          <LockKeyhole :size="22" />
          <div>
            <p class="overline">
              ACCOUNT ACCESS
            </p>
            <h2>登录工作台</h2>
          </div>
        </div>
        <label>
          <span>用户名</span>
          <input
            v-model="username"
            autocomplete="username"
            required
            maxlength="64"
          >
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="password"
            autocomplete="current-password"
            required
            minlength="8"
            type="password"
          >
        </label>
        <p
          v-if="error"
          class="form-error"
          role="alert"
        >
          {{ error }}
        </p>
        <button
          class="primary-button login-submit"
          type="submit"
          :disabled="auth.state.loading"
        >
          {{ auth.state.loading ? "正在登录" : "登录" }}
          <ArrowRight :size="18" />
        </button>
        <p class="demo-note">
          本地演示账号由 seed 命令创建，凭据见项目 README。
        </p>
      </form>
    </section>
  </main>
</template>
