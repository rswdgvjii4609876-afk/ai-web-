<template>
  <div>
    <div class="page-head">
      <div>
        <h1>管理员管理</h1>
        <p>只有拥有管理员管理权限的账号可以进入；授权开关仅 root 账号可修改。</p>
      </div>
      <input v-model="keyword" placeholder="搜索邮箱" @input="debouncedLoad" />
    </div>

    <div v-if="!authStore.canManageAdmins" class="card muted-card">
      当前账号没有管理员管理权限。
    </div>

    <div v-else class="admin-grid">
      <form class="card admin-form" @submit.prevent="handleSubmit">
        <h2>{{ editingId ? '编辑管理员' : '新增管理员' }}</h2>
        <label>邮箱<input v-model.trim="form.email" type="email" :disabled="editingIsRoot" required /></label>
        <label>名字<input v-model.trim="form.first_name" /></label>
        <label>姓氏<input v-model.trim="form.last_name" /></label>
        <label v-if="!editingId">初始密码<input v-model="form.password" type="password" minlength="8" required /></label>
        <label class="check-row">
          <input v-model="form.is_active" type="checkbox" :disabled="editingIsRoot" />
          启用账号
        </label>
        <label class="check-row">
          <input v-model="form.can_manage_admins" type="checkbox" :disabled="!authStore.isRootAdmin || editingIsRoot" />
          拥有管理员管理权限
        </label>
        <p v-if="!authStore.isRootAdmin" class="hint">只有原始账号可以授予或收回管理员管理权限。</p>
        <p v-if="message" class="message">{{ message }}</p>
        <div class="form-actions">
          <button class="btn-primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
          <button class="btn-sm" type="button" @click="resetForm">取消</button>
        </div>
      </form>

      <div class="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>邮箱</th>
              <th>姓名</th>
              <th>状态</th>
              <th>权限</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in admins" :key="item.id">
              <td>{{ item.id }}</td>
              <td>
                {{ item.email }}
                <span v-if="item.is_root_admin" class="badge badge-blue">root</span>
              </td>
              <td>{{ [item.first_name, item.last_name].filter(Boolean).join(' ') || '-' }}</td>
              <td><span :class="['badge', item.is_active ? 'badge-green' : 'badge-red']">{{ item.is_active ? '启用' : '禁用' }}</span></td>
              <td><span :class="['badge', item.can_manage_admins ? 'badge-yellow' : 'badge-blue']">{{ item.can_manage_admins ? '可管理管理员' : '普通管理员' }}</span></td>
              <td>{{ formatDate(item.created_at) }}</td>
              <td class="actions">
                <button class="btn-sm" @click="editAdmin(item)">编辑</button>
                <button class="btn-danger btn-sm" :disabled="item.is_root_admin || item.id === authStore.id" @click="deleteAdmin(item)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="pagination" v-if="total > perPage">
          <button class="btn-sm" :disabled="page <= 1" @click="page--; loadAdmins()">上一页</button>
          <span>{{ page }} / {{ Math.ceil(total / perPage) }}</span>
          <button class="btn-sm" :disabled="page >= Math.ceil(total / perPage)" @click="page++; loadAdmins()">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { adminApi, authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const admins = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const keyword = ref('')
const editingId = ref(null)
const saving = ref(false)
const message = ref('')
let timer = null

const emptyForm = () => ({
  email: '',
  first_name: '',
  last_name: '',
  password: '',
  is_active: true,
  can_manage_admins: false
})
const form = ref(emptyForm())
const editingIsRoot = computed(() => admins.value.some(item => item.id === editingId.value && item.is_root_admin))

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN')
}

function resetForm() {
  editingId.value = null
  form.value = emptyForm()
  message.value = ''
}

async function refreshMe() {
  const me = await authApi.me()
  authStore.setAdminInfo(me)
}

async function loadAdmins() {
  if (!authStore.canManageAdmins) return
  const data = await adminApi.list({
    page: page.value,
    per_page: perPage,
    email: keyword.value || undefined
  })
  admins.value = data.items || []
  total.value = data.total || 0
}

function debouncedLoad() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    page.value = 1
    loadAdmins()
  }, 300)
}

function editAdmin(item) {
  editingId.value = item.id
  form.value = {
    email: item.email || '',
    first_name: item.first_name || '',
    last_name: item.last_name || '',
    password: '',
    is_active: !!item.is_active,
    can_manage_admins: !!item.can_manage_admins
  }
  message.value = ''
}

async function handleSubmit() {
  message.value = ''
  saving.value = true
  try {
    if (editingId.value) {
      const payload = {
        email: form.value.email,
        first_name: form.value.first_name,
        last_name: form.value.last_name,
        is_active: form.value.is_active,
        can_manage_admins: form.value.can_manage_admins
      }
      await adminApi.update(editingId.value, payload)
      message.value = '管理员已更新'
    } else {
      await adminApi.create({ ...form.value })
      message.value = '管理员已创建'
    }
    await loadAdmins()
    resetForm()
  } catch (error) {
    message.value = error.message
  } finally {
    saving.value = false
  }
}

async function deleteAdmin(item) {
  if (!confirm(`确定删除管理员 ${item.email} 吗？此操作会同时清理后台登录 token。`)) return
  try {
    await adminApi.delete(item.id)
    await loadAdmins()
  } catch (error) {
    alert(error.message)
  }
}

onMounted(async () => {
  try {
    await refreshMe()
    await loadAdmins()
  } catch (error) {
    message.value = error.message
  }
})
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.page-head h1 { font-size: 20px; margin-bottom: 6px; }
.page-head p { color: #6b7280; font-size: 13px; }
.page-head input { width: 260px; }
.admin-grid { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 16px; align-items: start; }
.admin-form { display: flex; flex-direction: column; gap: 12px; }
.admin-form h2 { font-size: 16px; }
.admin-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.check-row { flex-direction: row !important; align-items: center; font-weight: 500 !important; }
.check-row input { width: auto; }
.hint { color: #6b7280; font-size: 12px; line-height: 1.5; }
.message { color: #111827; font-size: 13px; }
.form-actions { display: flex; gap: 8px; align-items: center; }
.actions { display: flex; gap: 8px; }
.actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.muted-card { color: #6b7280; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; padding-top: 16px; font-size: 13px; color: #6b7280; }
@media (max-width: 1000px) {
  .admin-grid { grid-template-columns: 1fr; }
  .page-head { flex-direction: column; }
  .page-head input { width: 100%; }
}
</style>
