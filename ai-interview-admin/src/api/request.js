import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1/backoffice'
const timeout = Number(import.meta.env.VITE_API_TIMEOUT || 30000)

const api = axios.create({ baseURL, timeout })
const downloadApi = axios.create({ baseURL, timeout, responseType: 'blob' })

const attachAuth = (config) => {
  const authStore = useAuthStore()
  if (authStore.token) config.headers.Authorization = `Bearer ${authStore.token}`
  return config
}

api.interceptors.request.use(attachAuth)
downloadApi.interceptors.request.use(attachAuth)

api.interceptors.response.use(
  res => {
    const data = res.data
    if (data.code === 200) return data.data
    return Promise.reject(new Error(data.message || '请求失败'))
  },
  err => {
    if (err.response?.status === 403 || err.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      router.push('/login')
    }
    const data = err.response?.data
    let msg = data?.message || err.message || '网络错误'
    if (data?.detail) {
      msg = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : data.detail
    }
    return Promise.reject(new Error(msg))
  }
)

downloadApi.interceptors.response.use(
  res => res,
  async err => {
    if (err.response?.status === 403 || err.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      router.push('/login')
    }
    let msg = err.message || '下载失败'
    if (err.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text()
        const parsed = JSON.parse(text)
        msg = parsed?.message || msg
      } catch {
        msg = '下载失败'
      }
    }
    return Promise.reject(new Error(msg))
  }
)

export { downloadApi }
export default api
