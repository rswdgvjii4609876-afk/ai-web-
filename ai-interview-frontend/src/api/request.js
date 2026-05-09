import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const timeout = Number(import.meta.env.VITE_API_TIMEOUT || 60000)

const api = axios.create({
  baseURL,
  timeout
})

const refreshClient = axios.create({
  baseURL,
  timeout
})

let refreshPromise = null

function isAuthRefreshRequest(config) {
  const url = config?.url || ''
  return url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh')
}

async function refreshAccessToken() {
  const authStore = useAuthStore()
  if (!authStore.refreshToken) {
    throw new Error('登录状态已失效，请重新登录')
  }

  const response = await refreshClient.post('/auth/refresh', {
    refresh_token: authStore.refreshToken
  })
  const payload = response.data

  if (payload?.code !== 200 || !payload?.data?.access_token) {
    throw new Error(payload?.message || '刷新登录状态失败')
  }

  authStore.setAccessToken(payload.data.access_token)
  return payload.data.access_token
}

api.interceptors.request.use(config => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

api.interceptors.response.use(
  response => {
    const data = response.data
    if (data.code === 200) {
      return data.data
    }
    return Promise.reject(new Error(data.message || '请求失败'))
  },
  async error => {
    const authStore = useAuthStore()
    const originalRequest = error.config || {}
    const status = error.response?.status

    if ((status === 401 || status === 403) && !originalRequest._retry && !isAuthRefreshRequest(originalRequest)) {
      originalRequest._retry = true
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const nextToken = await refreshPromise
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${nextToken}`
        return api(originalRequest)
      } catch (refreshError) {
        authStore.logout()
        router.push('/login')
        return Promise.reject(new Error(refreshError.message || '登录状态已失效，请重新登录'))
      } finally {
        refreshPromise = null
      }
    }

    if (status === 401 || status === 403) {
      authStore.logout()
      router.push('/login')
    }

    const data = error.response?.data
    let msg = data?.message || error.message || '网络错误'

    if (!error.response && error.message === 'Network Error') {
      msg = '网络连接失败，请稍后重试；如果反复失败，请检查服务状态、登录状态或简历文件大小'
    } else if (status === 502) {
      msg = '服务暂时不可用，请稍后重试'
    } else if (status === 413) {
      msg = '上传文件过大，请控制在 10MB 以内'
    }

    if (data?.detail) {
      if (Array.isArray(data.detail)) {
        msg = data.detail.map(item => item.msg || item.message || JSON.stringify(item)).join('; ')
      } else if (typeof data.detail === 'string') {
        msg = data.detail
      }
    }

    return Promise.reject(new Error(msg))
  }
)

export default api
