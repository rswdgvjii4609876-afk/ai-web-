import api from './request'

export function getTrainingReview(interviewId) {
  return api.get(`/training-reviews/${interviewId}`)
}

export function saveTrainingReview(interviewId, payload) {
  return api.put(`/training-reviews/${interviewId}`, payload)
}
