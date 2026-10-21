import { createRouter, createWebHistory } from "vue-router"

import { auth } from "./auth/store"
import AppShell from "./components/AppShell.vue"
import AssistantView from "./views/AssistantView.vue"
import DashboardView from "./views/DashboardView.vue"
import LoginView from "./views/LoginView.vue"
import NotFoundView from "./views/NotFoundView.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", name: "dashboard", component: DashboardView },
        { path: "assistant/:sessionId?", name: "assistant", component: AssistantView },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: NotFoundView,
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) {
    if (to.name === "login" && await auth.ensureLoaded()) return { name: "dashboard" }
    return true
  }
  if (await auth.ensureLoaded()) return true
  return { name: "login", query: { redirect: to.fullPath } }
})

export default router
