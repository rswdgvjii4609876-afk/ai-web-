import api from './request'

export function getKnowledgeBases(params = {}) {
  return api.get('/knowledge-bases', { params })
}

export function createKnowledgeBase(data) {
  return api.post('/knowledge-bases', data)
}

export function updateKnowledgeBase(knowledgeBaseId, data) {
  return api.put(`/knowledge-bases/${knowledgeBaseId}`, data)
}

export function getKnowledgeBaseSlices(knowledgeBaseId) {
  return api.get(`/knowledge-bases/${knowledgeBaseId}/slices`)
}

export function rebuildKnowledgeBaseSlices(knowledgeBaseId) {
  return api.post(`/knowledge-bases/${knowledgeBaseId}/slices/rebuild`)
}

export function deleteKnowledgeBase(knowledgeBaseId) {
  return api.delete(`/knowledge-bases/${knowledgeBaseId}`)
}
