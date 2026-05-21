import api from './request'

export function getLearningPlanOptions(params = {}) {
  return api.get('/learning-plans/options', { params })
}

export function generateLearningPlan(payload) {
  return api.post('/learning-plans/generate', payload)
}

export function getLearningPlan(planId) {
  return api.get(`/learning-plans/${encodeURIComponent(planId)}`)
}

export function updateLearningPlan(planId, payload) {
  return api.patch(`/learning-plans/${encodeURIComponent(planId)}`, payload)
}
