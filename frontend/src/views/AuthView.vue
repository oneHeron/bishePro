<template>
  <section class="auth-view card">
    <h1>Login / Register</h1>
    <p class="hint">Current User: {{ username || '未登录' }}</p>
    <form @submit.prevent="onSubmit">
      <label>Username <input v-model="form.username" required /></label>
      <label>Password <input v-model="form.password" type="password" required /></label>
      <div class="btn-row">
        <button type="button" @click="submit('register')">Register</button>
        <button type="button" @click="submit('login')">Login</button>
      </div>
    </form>
    <p :class="ok ? 'ok' : 'msg'">{{ msg }}</p>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { getUsername, setAuth } from '../stores/auth'

const route = useRoute()
const form = reactive({ username: '', password: '' })
const username = ref(getUsername())
const msg = ref('')
const ok = ref(false)

function onSubmit() {}

async function submit(action) {
  try {
    const fn = action === 'register' ? api.register : api.login
    const result = await fn(form)
    setAuth(result.token, result.username)
    username.value = result.username
    msg.value = `${action} 成功`
    ok.value = true
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    window.location.assign(redirect)
  } catch (err) {
    msg.value = err.message || '请求失败'
    ok.value = false
  }
}
</script>
