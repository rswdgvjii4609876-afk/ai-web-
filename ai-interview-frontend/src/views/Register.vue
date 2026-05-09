<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2>注册职启智评</h2>
      <p v-if="!verificationStep" class="subtitle">创建账号开始简历诊断、岗位匹配与模拟面试</p>
      <p v-else class="subtitle">请输入发送到邮箱的 6 位验证码，完成注册</p>

      <form v-if="!verificationStep" @submit.prevent="handleRegister">
        <div class="form-row">
          <div class="form-group">
            <label>名</label>
            <input v-model="form.first_name" placeholder="名" required />
          </div>
          <div class="form-group">
            <label>姓</label>
            <input v-model="form.last_name" placeholder="姓" required />
          </div>
        </div>
        <div class="form-group">
          <label>邮箱</label>
          <input v-model="form.email" type="email" placeholder="请输入邮箱" required />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="form.password" type="password" placeholder="至少8位，含字母+数字+特殊字符" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="success" class="success">{{ success }}</p>
        <button type="submit" class="btn-glow" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>

      <form v-else @submit.prevent="handleVerifyEmail">
        <div class="verification-hint">
          当前邮箱：<strong>{{ pendingEmail }}</strong>
        </div>
        <div class="form-group">
          <label>验证码</label>
          <input
            v-model="verificationCode"
            inputmode="numeric"
            maxlength="6"
            placeholder="请输入 6 位验证码"
            required
          />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="success" class="success">{{ success }}</p>
        <button type="submit" class="btn-glow" :disabled="loading">
          {{ loading ? '验证中...' : '验证并登录' }}
        </button>
        <button type="button" class="btn-secondary" :disabled="loading" @click="handleResendCode">
          重新发送验证码
        </button>
        <button type="button" class="btn-link" :disabled="loading" @click="backToRegister">
          返回修改邮箱
        </button>
      </form>
      <p class="auth-link">已有账号？<router-link to="/login">去登录</router-link></p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { register, sendVerificationCode, verifyEmail } from '../api/auth'

const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ first_name: '', last_name: '', email: '', password: '' })
const error = ref('')
const success = ref('')
const loading = ref(false)
const verificationStep = ref(false)
const verificationCode = ref('')
const pendingEmail = ref('')

async function handleRegister() {
  error.value = ''; success.value = ''; loading.value = true
  try {
    const res = await register(form)
    if (res?.access_token && res?.refresh_token) {
      authStore.setAuth(res)
      success.value = '注册成功，正在跳转...'
      setTimeout(() => router.push('/dashboard'), 800)
      return
    }

    if (res?.verification_required) {
      pendingEmail.value = res.email || form.email
      verificationStep.value = true
      verificationCode.value = ''
      success.value = res.message || '注册成功，请输入邮箱验证码完成注册'
      return
    }

    throw new Error('注册接口返回了未识别的数据结构')
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}

async function handleVerifyEmail() {
  error.value = ''; success.value = ''; loading.value = true
  try {
    const res = await verifyEmail(pendingEmail.value, verificationCode.value)
    authStore.setAuth(res)
    success.value = '邮箱验证成功，正在跳转...'
    setTimeout(() => router.push('/dashboard'), 800)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function handleResendCode() {
  error.value = ''; success.value = ''; loading.value = true
  try {
    const res = await sendVerificationCode(pendingEmail.value, 'registration')
    success.value = res.message || '验证码已重新发送'
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function backToRegister() {
  verificationStep.value = false
  verificationCode.value = ''
  error.value = ''
  success.value = ''
}
</script>

<style scoped>
.auth-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%); }
.auth-card { width: 420px; background: white; border-radius: 16px; padding: 36px; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
.auth-card h2 { font-size: 24px; color: #4f46e5; margin-bottom: 4px; }
.subtitle { color: #6b7280; margin-bottom: 24px; font-size: 14px; }
.form-row { display: flex; gap: 12px; }
.form-group { margin-bottom: 16px; text-align: left; flex: 1; }
.form-group label { display: block; margin-bottom: 6px; font-size: 14px; font-weight: 500; color: #374151; }
.form-group input { width: 100%; padding: 11px 14px; border: 1px solid #e5e7eb; border-radius: 10px; font-size: 14px; outline: none; transition: all 0.3s; background: #f9fafb; }
.form-group input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); background: white; }
.error { color: #ef4444; font-size: 13px; margin-bottom: 12px; }
.success { color: #10b981; font-size: 13px; margin-bottom: 12px; }
.verification-hint { margin-bottom: 16px; color: #475569; font-size: 14px; text-align: left; }
.btn-glow { width: 100%; padding: 12px; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; color: white; background: linear-gradient(135deg, #4f46e5, #7c3aed, #6366f1); background-size: 200% 200%; animation: gradientShift 3s ease infinite; cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 15px rgba(79,70,229,0.4); }
.btn-glow:hover { transform: translateY(-1px); box-shadow: 0 6px 25px rgba(79,70,229,0.5); }
.btn-glow:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.btn-secondary { width: 100%; margin-top: 10px; padding: 11px; border: 1px solid #dbe3f0; border-radius: 10px; font-size: 14px; font-weight: 600; color: #334155; background: #f8fafc; cursor: pointer; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-link { margin-top: 12px; border: none; background: transparent; color: #4f46e5; font-size: 14px; cursor: pointer; }
@keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
.auth-link { margin-top: 18px; font-size: 14px; color: #6b7280; }
.auth-link a { color: #4f46e5; font-weight: 500; }
</style>
