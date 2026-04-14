<template>
  <div class="app-shell">
    <header class="site-header">
      <RouterLink class="brand" to="/">
        <span class="brand-topline">
          <span class="brand-logo" aria-hidden="true">
            <span class="brand-logo-core">O</span>
            <span class="brand-logo-ring brand-logo-ring-a"></span>
            <span class="brand-logo-ring brand-logo-ring-b"></span>
          </span>
          <span class="brand-wording">
            <span class="brand-wordmark">OpenCDP</span>
            <span class="brand-tag">Community Detection Platform</span>
          </span>
        </span>
        <span class="brand-mark">社区检测集成平台</span>
      </RouterLink>
      <nav class="site-nav">
        <RouterLink to="/catalog/methods">方法库</RouterLink>
        <RouterLink to="/catalog/datasets">数据集</RouterLink>
        <RouterLink to="/catalog/metrics">评价指标</RouterLink>
        <RouterLink to="/history">运行历史</RouterLink>
        <RouterLink to="/run">发起运行</RouterLink>
      </nav>
      <div class="auth-block">
        <RouterLink
          v-if="!token"
          class="auth-btn"
          :to="{ path: '/auth' }"
        >
          登录 / 注册
        </RouterLink>
        <template v-else>
          <span class="user-chip">当前用户：{{ username }}</span>
          <button class="auth-btn" @click="logout">退出登录</button>
        </template>
      </div>
    </header>
    <main class="page-wrap">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { clearAuth, getToken, getUsername } from './stores/auth'
import { clearRunHistory } from './stores/history'

const route = useRoute()
const router = useRouter()
const token = ref('')
const username = ref('')

function refreshAuth() {
  token.value = getToken()
  username.value = getUsername()
}

function logout() {
  clearAuth()
  clearRunHistory()
  refreshAuth()
  router.push('/auth')
}

watch(
  () => route.fullPath,
  () => refreshAuth(),
  { immediate: true }
)

onMounted(() => {
  window.addEventListener('storage', refreshAuth)
})

onUnmounted(() => {
  window.removeEventListener('storage', refreshAuth)
})
</script>
