import api from './request'

export function getLearningTasks() {
  return api.get('/learning-tasks')
}

export function bulkUpsertLearningTasks(tasks, options = {}) {
  return api.post('/learning-tasks/bulk-upsert', {
    tasks,
    replace_progress: Boolean(options.replaceProgress)
  })
}

export function patchLearningTask(taskKey, patch) {
  return api.patch(`/learning-tasks/${encodeURIComponent(taskKey)}`, patch)
}

export function deleteLearningTask(taskKey) {
  return api.delete(`/learning-tasks/${encodeURIComponent(taskKey)}`)
}
