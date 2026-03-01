<template>
  <div class="app-shell">
    <header class="site-header">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">OpenCDP</span>
        <span class="brand-sub">Open Community Detection Platform</span>
      </RouterLink>
      <nav class="site-nav">
        <RouterLink to="/catalog/methods">Methods</RouterLink>
        <RouterLink to="/catalog/datasets">Datasets</RouterLink>
        <RouterLink to="/catalog/metrics">Metrics</RouterLink>
        <RouterLink to="/history">History</RouterLink>
        <RouterLink to="/run">Run</RouterLink>
      </nav>
      <div class="auth-block">
        <RouterLink
          v-if="!token"
          class="auth-btn"
          :to="{ path: '/auth', query: { redirect: route.fullPath } }"
        >
          Login/Register
        </RouterLink>
        <template v-else>
          <span class="user-chip">{{ username }}</span>
          <button class="auth-btn" @click="logout">Logout</button>
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
