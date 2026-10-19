import api from './request'
export const listFeedback = (offset = 0) => api.get('/feedback', { params: { offset, limit: 20 } })
export const createFeedback = payload => api.post('/feedback', payload)
