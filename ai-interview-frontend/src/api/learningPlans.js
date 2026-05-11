import api from './request'

export function getLearningPlanOptions(params = {}) {
  return api.get('/learning-plans/options', { params })
}

export function generateLearningPlan(payload) {
  return api.post('/learning-plans/generate', payload)
}
