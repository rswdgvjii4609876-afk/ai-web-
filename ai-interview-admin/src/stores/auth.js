import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('admin_token') || '')
  const email = ref(localStorage.getItem('admin_email') || '')
  const id = ref(Number(localStorage.getItem('admin_id') || 0))
  const role = ref(localStorage.getItem('admin_role') || '')
  const firstName = ref(localStorage.getItem('admin_first_name') || '')
  const lastName = ref(localStorage.getItem('admin_last_name') || '')
  const canManageAdmins = ref(localStorage.getItem('admin_can_manage_admins') === 'true')
  const isRootAdmin = ref(localStorage.getItem('admin_is_root_admin') === 'true')

  const isLoggedIn = computed(() => !!token.value)

  function setAuth(data) {
    token.value = data.access_token
    email.value = data.email || ''
    localStorage.setItem('admin_token', data.access_token)
    localStorage.setItem('admin_email', email.value)
  }

  function setAdminInfo(data) {
    id.value = Number(data.id || 0)
    email.value = data.email || email.value
    role.value = data.role || ''
    firstName.value = data.first_name || ''
    lastName.value = data.last_name || ''
    canManageAdmins.value = !!data.can_manage_admins
    isRootAdmin.value = !!data.is_root_admin
    localStorage.setItem('admin_id', String(id.value || ''))
    localStorage.setItem('admin_email', email.value)
    localStorage.setItem('admin_role', role.value)
    localStorage.setItem('admin_first_name', firstName.value)
    localStorage.setItem('admin_last_name', lastName.value)
    localStorage.setItem('admin_can_manage_admins', String(canManageAdmins.value))
    localStorage.setItem('admin_is_root_admin', String(isRootAdmin.value))
  }

  function logout() {
    token.value = ''
    email.value = ''
    id.value = 0
    role.value = ''
    firstName.value = ''
    lastName.value = ''
    canManageAdmins.value = false
    isRootAdmin.value = false
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_email')
    localStorage.removeItem('admin_id')
    localStorage.removeItem('admin_role')
    localStorage.removeItem('admin_first_name')
    localStorage.removeItem('admin_last_name')
    localStorage.removeItem('admin_can_manage_admins')
    localStorage.removeItem('admin_is_root_admin')
  }

  return {
    token,
    email,
    id,
    role,
    firstName,
    lastName,
    canManageAdmins,
    isRootAdmin,
    isLoggedIn,
    setAuth,
    setAdminInfo,
    logout
  }
})
