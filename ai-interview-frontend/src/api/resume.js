import api from './request'

export function uploadResume(file, targetPosition, options = {}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('target_position', targetPosition)
  if (options.provider) {
    formData.append('ai_provider', options.provider)
  }
  if (options.model) {
    formData.append('ai_model', options.model)
  }
  return api.post('/resumes/upload', formData, {
    timeout: 120000
  })
}

export function getResume(resumeId) {
  return api.get(`/resumes/${resumeId}`)
}

export function getResumes() {
  return api.get('/resumes')
}
