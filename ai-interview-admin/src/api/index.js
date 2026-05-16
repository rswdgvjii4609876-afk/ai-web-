import api, { downloadApi } from './request'

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me')
}

export const adminApi = {
  list: (params) => api.get('/admins', { params }),
  create: (data) => api.post('/admins', data),
  update: (id, data) => api.put(`/admins/${id}`, data),
  delete: (id) => api.delete(`/admins/${id}`),
  changePassword: (id, data) => api.post(`/admins/${id}/change-password`, data)
}

export const userApi = {
  list: (params) => api.get('/users', { params }),
  stats: () => api.get('/users/stats'),
  toggleActive: (id) => api.put(`/users/${id}/toggle-active`)
}

export const interviewApi = {
  list: (params) => api.get('/interviews', { params }),
  detail: (id) => api.get(`/interviews/${id}`),
  trainingSample: (id, params) => api.get(`/interviews/${id}/training-sample`, { params }),
  updateTrainingReview: (id, data) => api.put(`/interviews/${id}/training-sample-review`, data),
  evaluationDatasetPreview: (params) => api.get('/interviews/evaluation-datasets/preview', { params }),
  exportEvaluationDatasets: (params) => downloadApi.get('/interviews/evaluation-datasets/export', { params }),
  exportFineTuningSamples: (params) => downloadApi.get('/interviews/evaluation-datasets/fine-tuning/export', { params }),
  delete: (id) => api.delete(`/interviews/${id}`)
}

export const knowledgeBaseApi = {
  list: () => api.get('/knowledge-bases'),
  create: (data) => api.post('/knowledge-bases', data),
  update: (id, data) => api.put(`/knowledge-bases/${id}`, data),
  slices: (id) => api.get(`/knowledge-bases/${id}/slices`),
  rebuildSlices: (id) => api.post(`/knowledge-bases/${id}/slices/rebuild`),
  delete: (id) => api.delete(`/knowledge-bases/${id}`)
}

export const learningRouteApi = {
  list: (params) => api.get('/learning-routes', { params }),
  coverage: () => api.get('/learning-routes/coverage'),
  create: (data) => api.post('/learning-routes', data),
  bulkUpsert: (data) => api.post('/learning-routes/bulk-upsert', data),
  duplicate: (id) => api.post(`/learning-routes/${id}/duplicate`),
  previewTask: (data) => api.post('/learning-routes/preview-task', data),
  update: (id, data) => api.put(`/learning-routes/${id}`, data),
  delete: (id) => api.delete(`/learning-routes/${id}`)
}
