<template>
  <div class="login-page">
    <div class="login-card">
      <h2>职启智评管理后台</h2>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>邮箱</label>
          <input v-model="email" type="email" placeholder="admin@ai-interview.com" required />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="密码" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" class="login-submit" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { authApi } from '../api'

const router = useRouter()
const authStore = useAuthStore()
const email = ref('admin@ai-interview.com')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''; loading.value = true
  try {
    const data = await authApi.login(email.value, password.value)
    authStore.setAuth({ ...data, email: email.value })
    router.push('/')
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: #f3f4f6; }
.login-card { width: 400px; background: white; border-radius: 12px; padding: 40px 36px; text-align: center; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.login-card h2 { font-size: 24px; color: #111827; margin-bottom: 28px; }
.form-group { margin-bottom: 18px; text-align: left; }
.form-group label { display: block; margin-bottom: 6px; font-size: 14px; font-weight: 500; color: #374151; }
.form-group input { width: 100%; padding: 11px 14px; border: 1px solid #e5e7eb; border-radius: 10px; font-size: 14px; outline: none; transition: all 0.3s; background: #f9fafb; }
.form-group input:focus { border-color: #111827; box-shadow: 0 0 0 3px rgba(17,24,39,0.08); background: white; }
.error { color: #ef4444; font-size: 13px; margin-bottom: 12px; }
.login-submit { width: 100%; padding: 12px; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; color: white; background: #111827; cursor: pointer; transition: all 0.2s; box-shadow: none; }
.login-submit:hover { background: #000000; }
.login-submit:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
</style>
