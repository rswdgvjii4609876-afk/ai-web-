<template>
  <div class="container">
    <div class="profile-page">
      <h2 class="page-title">个人设置</h2>

      <div class="card avatar-section">
        <div class="avatar-wrapper" @click="$refs.avatarInput.click()">
          <img v-if="profile.avatar" :src="avatarUrl" class="avatar-img" alt="avatar" />
          <div v-else class="avatar-placeholder">{{ initials }}</div>
          <div class="avatar-overlay">上传</div>
          <input ref="avatarInput" type="file" accept="image/*" @change="handleAvatarChange" hidden />
        </div>
        <div class="avatar-info">
          <p class="avatar-name">{{ displayName }}</p>
          <p class="avatar-email">{{ profile.email }}</p>
        </div>
        <div class="provider-actions" style="margin-top: 12px">
          <button
            class="btn-secondary"
            @click="handleTestAiConnection"
            :disabled="saving || testingAiConnection"
          >
            {{ testingAiConnection ? '测试中...' : `测试当前 ${activeProviderLabel} 连接` }}
          </button>
          <p v-if="testAiMessage" :class="testAiSuccess ? 'success-msg' : 'error'">
            {{ testAiMessage }}
          </p>
        </div>
      </div>

      <div class="card" style="margin-top: 16px">
        <h3 class="section-title">基本信息</h3>
        <div class="form-row">
          <div class="form-group">
            <label>姓</label>
            <input v-model="form.last_name" placeholder="请输入姓氏" />
          </div>
          <div class="form-group">
            <label>名</label>
            <input v-model="form.first_name" placeholder="请输入名字" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>性别</label>
            <select v-model="form.gender">
              <option value="">未设置</option>
              <option value="male">男</option>
              <option value="female">女</option>
            </select>
          </div>
          <div class="form-group">
            <label>手机号</label>
            <input v-model="form.phone" placeholder="请输入手机号" />
          </div>
        </div>
        <div class="form-group">
          <label>学校</label>
          <input v-model="form.university" placeholder="请输入学校名称" />
        </div>
        <div class="form-group">
          <label>求职目标</label>
          <input v-model="form.career_goal" placeholder="例如：Python后端开发工程师 / 测试工程师 / 产品助理 / 人力资源专员" />
        </div>
        <div class="form-group">
          <label>所在城市</label>
          <input v-model="form.location" placeholder="例如：上海" />
        </div>
      </div>

      <div class="card" style="margin-top: 16px">
        <div class="section-head">
          <div>
            <h3 class="section-title">AI 调用设置</h3>
            <p class="section-desc">
              你可以在这里选择使用 DeepSeek 或 ChatGPT / OpenAI，并分别保存自己的 API Key。
              当前被选中的服务商将用于简历解析、岗位画像匹配、模拟面试和报告生成；如遇 Token 无效、额度不足或连接失败，页面会直接提示原因。
            </p>
          </div>
          <div class="provider-status-list">
            <span :class="['status-chip', profile.deepseek_has_personal_api_key ? 'status-on' : 'status-off']">
              DeepSeek {{ profile.deepseek_has_personal_api_key ? '已保存' : '未保存' }}
            </span>
            <span :class="['status-chip', profile.openai_has_personal_api_key ? 'status-on' : 'status-off']">
              ChatGPT {{ profile.openai_has_personal_api_key ? '已保存' : '未保存' }}
            </span>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>当前服务商</label>
            <select v-model="form.ai_provider">
              <option v-for="option in providerOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>模型</label>
            <input
              v-model="activeModelValue"
              :placeholder="activeModelPlaceholder"
              :list="modelDatalistId"
            />
            <datalist :id="modelDatalistId">
              <option
                v-for="option in activeModelOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </datalist>
          </div>
        </div>

        <div class="form-group">
          <label>{{ activeProviderLabel }} API Key</label>
          <input
            v-model="providerApiKeyInputs[activeProvider]"
            type="password"
            :placeholder="`输入新的 ${activeProviderLabel} API Key；已保存的 Key 不会回显`"
          />
          <p class="field-tip">
            已保存的 Key 不会回显。留空表示本次不修改；如果你切换服务商，请先为该服务商保存对应的 Key。
          </p>
        </div>

        <div class="form-group">
          <label>Base URL</label>
          <input
            v-model="activeBaseUrlValue"
            :placeholder="`默认：${activeBaseUrlPlaceholder}`"
          />
        </div>

        <div class="provider-actions">
          <button
            class="btn-secondary"
            @click="handleClearSavedKey"
            :disabled="!activeProviderHasSavedKey || saving"
          >
            删除当前服务商已保存 Key
          </button>
          <p v-if="clearSavedKeyPending[activeProvider]" class="field-tip warning-tip">
            本次保存后会删除当前服务商在服务器中已保存的 API Key。
          </p>
        </div>
      </div>

      <div class="card" style="margin-top: 16px">
        <h3 class="section-title">修改密码</h3>
        <div class="form-group">
          <label>当前密码</label>
          <input v-model="pwForm.old_password" type="password" placeholder="请输入当前密码" />
        </div>
        <div class="form-group">
          <label>新密码</label>
          <input v-model="pwForm.new_password" type="password" placeholder="至少 6 位" />
        </div>
        <div class="form-group">
          <label>确认新密码</label>
          <input v-model="pwForm.confirm_password" type="password" placeholder="请再次输入新密码" />
        </div>
        <p v-if="pwMsg" :class="pwMsg.startsWith('✅') ? 'success-msg' : 'error'">{{ pwMsg }}</p>
        <button class="btn-primary" style="width: 100%; margin-top: 8px" @click="handleChangePassword" :disabled="changingPw">
          {{ changingPw ? '修改中...' : '修改密码' }}
        </button>
      </div>

      <div class="card" style="margin-top: 16px">
        <div class="section-head">
          <div>
            <h3 class="section-title">隐私与数据授权</h3>
            <p class="section-desc">
              基础隐私协议用于提供简历解析、润色和模拟面试；数据贡献授权用于系统评测、比赛材料、
              质量改进和数据集沉淀，默认可撤回后续使用。
            </p>
          </div>
          <span :class="['status-chip', privacyForm.privacy_agreed ? 'status-on' : 'status-off']">
            {{ privacyForm.privacy_agreed ? '已同意基础协议' : '待同意基础协议' }}
          </span>
        </div>
        <p class="field-tip">
          当前协议版本：{{ profile.privacy_policy_version || '未记录' }}；
          同意时间：{{ formatConsentTime(profile.privacy_agreed_at) }}
        </p>
        <label v-if="!profile.privacy_agreed_at" class="privacy-setting-check required">
          <input v-model="privacyForm.privacy_agreed" type="checkbox" />
          <span>
            我已阅读并同意
            <router-link to="/privacy" target="_blank">《隐私协议与个人信息处理说明》</router-link>
          </span>
        </label>
        <label class="privacy-setting-check">
          <input v-model="privacyForm.data_contribution_consent" type="checkbox" />
          <span>
            同意后续将去标识化后的简历、学校/专业/项目经历、目标岗位、面试问答、报告和人工评分用于
            系统评测、比赛材料、质量改进和数据集沉淀。
          </span>
        </label>
        <p class="field-tip">
          数据贡献授权状态：{{ privacyForm.data_contribution_consent ? '已开启' : '未开启或已撤回' }}；
          最近授权时间：{{ formatConsentTime(profile.data_contribution_consent_at) }}；
          最近撤回时间：{{ formatConsentTime(profile.data_contribution_withdrawn_at) }}。
        </p>
      </div>

      <p v-if="profileMsg" :class="profileMsg.startsWith('✅') ? 'success-msg page-msg' : 'error page-msg'">
        {{ profileMsg }}
      </p>
      <button class="btn-primary save-btn" @click="handleSaveProfile" :disabled="saving">
        {{ saving ? '保存中...' : '保存资料' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { useAuthStore } from '../stores/auth'
import { changePassword, getProfile, testAiConnection, updateProfile, uploadAvatar } from '../api/user'

const authStore = useAuthStore()

const providerOptions = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'ChatGPT / OpenAI' }
]

const providerLabels = {
  deepseek: 'DeepSeek',
  openai: 'ChatGPT / OpenAI'
}

const providerDefaults = {
  deepseek: {
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-v4-flash'
  },
  openai: {
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-5.2-chat-latest'
  }
}

const providerModelOptions = {
  deepseek: [
    { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash（推荐）' },
    { value: 'deepseek-v4-pro', label: 'deepseek-v4-pro' },
    { value: 'deepseek-chat', label: 'deepseek-chat（旧版兼容，2026-07-24 停用）' },
    { value: 'deepseek-reasoner', label: 'deepseek-reasoner（旧版兼容，2026-07-24 停用）' }
  ],
  openai: [
    { value: 'gpt-5.2-chat-latest', label: 'gpt-5.2-chat-latest' },
    { value: 'gpt-5.2', label: 'gpt-5.2' },
    { value: 'gpt-5-mini', label: 'gpt-5-mini' }
  ]
}

const modelDatalistId = 'provider-model-options'

const profile = ref({})
const form = ref({
  first_name: '',
  last_name: '',
  gender: '',
  phone: '',
  university: '',
  career_goal: '',
  location: '',
  ai_provider: 'deepseek',
  deepseek_base_url: '',
  deepseek_model: '',
  openai_base_url: '',
  openai_model: ''
})
const providerApiKeyInputs = ref({
  deepseek: '',
  openai: ''
})
const clearSavedKeyPending = ref({
  deepseek: false,
  openai: false
})
const pwForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const privacyForm = ref({ privacy_agreed: false, data_contribution_consent: false })
const saving = ref(false)
const changingPw = ref(false)
const profileMsg = ref('')
const pwMsg = ref('')
const testingAiConnection = ref(false)
const testAiMessage = ref('')
const testAiSuccess = ref(false)

const avatarUrl = computed(() => {
  if (!profile.value.avatar) return ''
  if (profile.value.avatar.startsWith('http')) return profile.value.avatar
  return profile.value.avatar
})

const initials = computed(() => {
  const firstName = profile.value.first_name || ''
  const lastName = profile.value.last_name || ''
  return (lastName.charAt(0) + firstName.charAt(0)).toUpperCase() || '我'
})

const displayName = computed(() => {
  return `${profile.value.last_name || ''}${profile.value.first_name || ''}`.trim() || profile.value.email || '用户'
})

const activeProvider = computed(() => form.value.ai_provider || 'deepseek')
const activeProviderLabel = computed(() => providerLabels[activeProvider.value] || 'AI')
const activeModelOptions = computed(() => providerModelOptions[activeProvider.value] || [])
const activeModelPlaceholder = computed(() => providerDefaults[activeProvider.value]?.model || '')
const activeBaseUrlPlaceholder = computed(() => providerDefaults[activeProvider.value]?.baseUrl || '')
const activeProviderHasSavedKey = computed(() => {
  if (activeProvider.value === 'openai') {
    return !!profile.value.openai_has_personal_api_key
  }
  return !!profile.value.deepseek_has_personal_api_key
})

const activeModelValue = computed({
  get() {
    if (activeProvider.value === 'openai') {
      return form.value.openai_model
    }
    return form.value.deepseek_model
  },
  set(value) {
    if (activeProvider.value === 'openai') {
      form.value.openai_model = value
    } else {
      form.value.deepseek_model = value
    }
  }
})

const activeBaseUrlValue = computed({
  get() {
    if (activeProvider.value === 'openai') {
      return form.value.openai_base_url
    }
    return form.value.deepseek_base_url
  },
  set(value) {
    if (activeProvider.value === 'openai') {
      form.value.openai_base_url = value
    } else {
      form.value.deepseek_base_url = value
    }
  }
})

function applyProfile(data) {
  profile.value = data || {}
  privacyForm.value = {
    privacy_agreed: Boolean(data.privacy_agreed_at),
    data_contribution_consent: Boolean(data.data_contribution_consent)
  }
  form.value = {
    first_name: data.first_name || '',
    last_name: data.last_name || '',
    gender: data.gender || '',
    phone: data.phone || '',
    university: data.university || '',
    career_goal: data.career_goal || '',
    location: data.location || '',
    ai_provider: data.ai_provider || 'deepseek',
    deepseek_base_url: data.deepseek_base_url || '',
    deepseek_model: data.deepseek_model || '',
    openai_base_url: data.openai_base_url || '',
    openai_model: data.openai_model || ''
  }
  providerApiKeyInputs.value = {
    deepseek: '',
    openai: ''
  }
  clearSavedKeyPending.value = {
    deepseek: false,
    openai: false
  }
  authStore.setUserInfo(data)
}

function formatConsentTime(value) {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

async function loadProfile() {
  const data = await getProfile()
  applyProfile(data)
}

onMounted(async () => {
  try {
    await loadProfile()
  } catch (error) {
    console.error(error)
  }
})

async function handleAvatarChange(event) {
  const file = event.target.files[0]
  if (!file) return
  try {
    const data = await uploadAvatar(file)
    profile.value.avatar = data.avatar
    authStore.setUserInfo(profile.value)
  } catch (error) {
    alert(`头像上传失败：${error.message}`)
  }
}

function handleClearSavedKey() {
  clearSavedKeyPending.value[activeProvider.value] = true
  providerApiKeyInputs.value[activeProvider.value] = ''
  profileMsg.value = `✅ 已标记删除 ${activeProviderLabel.value} Key，点击“保存资料”后生效`
}

async function handleSaveProfile() {
  profileMsg.value = ''
  testAiMessage.value = ''
  saving.value = true
  try {
    const payload = {
      first_name: form.value.first_name.trim(),
      last_name: form.value.last_name.trim(),
      phone: form.value.phone.trim(),
      university: form.value.university.trim(),
      career_goal: form.value.career_goal.trim(),
      location: form.value.location.trim(),
      gender: form.value.gender,
      ai_provider: form.value.ai_provider,
      deepseek_base_url: form.value.deepseek_base_url.trim(),
      deepseek_model: form.value.deepseek_model.trim(),
      openai_base_url: form.value.openai_base_url.trim(),
      openai_model: form.value.openai_model.trim()
    }

    if (providerApiKeyInputs.value.deepseek.trim()) {
      payload.deepseek_api_key = providerApiKeyInputs.value.deepseek.trim()
    }
    if (providerApiKeyInputs.value.openai.trim()) {
      payload.openai_api_key = providerApiKeyInputs.value.openai.trim()
    }
    if (clearSavedKeyPending.value.deepseek) {
      payload.clear_deepseek_api_key = true
    }
    if (clearSavedKeyPending.value.openai) {
      payload.clear_openai_api_key = true
    }
    if (!profile.value.privacy_agreed_at && privacyForm.value.privacy_agreed) {
      payload.privacy_agreed = true
    }
    if (Boolean(profile.value.data_contribution_consent) !== Boolean(privacyForm.value.data_contribution_consent)) {
      payload.data_contribution_consent = Boolean(privacyForm.value.data_contribution_consent)
    }

    const result = await updateProfile(payload)
    await loadProfile()
    profileMsg.value = `✅ ${result.message || '保存成功'}`
  } catch (error) {
    profileMsg.value = error.message
  } finally {
    saving.value = false
  }
}

async function handleTestAiConnection() {
  testAiMessage.value = ''
  testAiSuccess.value = false
  testingAiConnection.value = true
  try {
    const result = await testAiConnection(activeProvider.value)
    testAiSuccess.value = true
    testAiMessage.value = result?.message || `${activeProviderLabel.value} 连接测试成功`
  } catch (error) {
    testAiMessage.value = error.message
  } finally {
    testingAiConnection.value = false
  }
}

async function handleChangePassword() {
  pwMsg.value = ''
  if (pwForm.value.new_password !== pwForm.value.confirm_password) {
    pwMsg.value = '两次输入的新密码不一致'
    return
  }
  if (pwForm.value.new_password.length < 6) {
    pwMsg.value = '新密码至少 6 位'
    return
  }
  changingPw.value = true
  try {
    await changePassword(pwForm.value.old_password, pwForm.value.new_password)
    pwMsg.value = '✅ 密码修改成功'
    pwForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (error) {
    pwMsg.value = error.message
  } finally {
    changingPw.value = false
  }
}
</script>

<style scoped>
.profile-page {
  max-width: 640px;
  margin: 20px auto 40px;
}

.page-title {
  margin-bottom: 24px;
}

.section-title {
  margin-bottom: 16px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-desc {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.7;
}

.provider-status-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  position: relative;
  cursor: pointer;
  overflow: hidden;
  flex-shrink: 0;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.2s;
}

.avatar-wrapper:hover .avatar-overlay {
  opacity: 1;
}

.avatar-name {
  font-size: 18px;
  font-weight: 600;
}

.avatar-email {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-group {
  margin-bottom: 14px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.field-tip {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}

.warning-tip {
  color: #b45309;
}

.privacy-setting-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  color: #1f2937;
  font-size: 13px;
  line-height: 1.6;
}

.privacy-setting-check input {
  margin-top: 3px;
  flex-shrink: 0;
}

.privacy-setting-check.required {
  font-weight: 600;
}

.privacy-setting-check a {
  color: #2563eb;
  font-weight: 600;
}

.provider-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-chip {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.status-on {
  background: #dcfce7;
  color: #166534;
}

.status-off {
  background: #f3f4f6;
  color: #6b7280;
}

.error {
  color: #ef4444;
  font-size: 13px;
  margin-top: 8px;
}

.success-msg {
  color: #059669;
  font-size: 13px;
  margin-top: 8px;
}

.page-msg {
  margin-top: 16px;
}

.save-btn {
  width: 100%;
  margin-top: 12px;
}

@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .section-head,
  .provider-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .provider-status-list {
    justify-content: flex-start;
  }
}
</style>
