<template>
  <div class="account-page">
    <div class="card account-card">
      <h1>账号设置</h1>
      <p class="muted">修改当前后台管理员账号密码。系统不会保存明文密码。</p>

      <div class="profile-box">
        <div><span>邮箱</span><strong>{{ authStore.email || '-' }}</strong></div>
        <div><span>权限</span><strong>{{ authStore.canManageAdmins ? '可管理管理员' : '普通管理员' }}</strong></div>
      </div>

      <form @submit.prevent="changePassword">
        <label>当前密码<input v-model="form.current_password" type="password" required /></label>
        <label>新密码<input v-model="form.new_password" type="password" minlength="8" required /></label>
        <label>确认新密码<input v-model="confirmPassword" type="password" minlength="8" required /></label>
        <p v-if="message" :class="['message', success ? 'ok' : 'bad']">{{ message }}</p>
        <button class="btn-primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '修改密码' }}</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { adminApi, authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const saving = ref(false)
const message = ref('')
const success = ref(false)
const confirmPassword = ref('')
const form = ref({
  current_password: '',
  new_password: ''
})

async function refreshMe() {
  const me = await authApi.me()
  authStore.setAdminInfo(me)
}

async function changePassword() {
  message.value = ''
  success.value = false
  if (form.value.new_password !== confirmPassword.value) {
    message.value = '两次输入的新密码不一致'
    return
  }
  saving.value = true
  try {
    await adminApi.changePassword(authStore.id, form.value)
    form.value = { current_password: '', new_password: '' }
    confirmPassword.value = ''
    success.value = true
    message.value = '密码已修改，请下次登录使用新密码'
  } catch (error) {
    message.value = error.message
  } finally {
    saving.value = false
  }
}

onMounted(refreshMe)
</script>

<style scoped>
.account-page { max-width: 640px; }
.account-card h1 { font-size: 20px; margin-bottom: 8px; }
.muted { color: #6b7280; font-size: 13px; margin-bottom: 18px; }
.profile-box { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }
.profile-box div { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.profile-box span { display: block; color: #6b7280; font-size: 12px; margin-bottom: 4px; }
.profile-box strong { font-size: 14px; }
form { display: flex; flex-direction: column; gap: 14px; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.message { font-size: 13px; }
.message.ok { color: #047857; }
.message.bad { color: #dc2626; }
button { width: fit-content; }
</style>
