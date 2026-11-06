import api from './request'

function taskPayload(task) {
  const payload = { ...task }
  for (const field of ['resume_id', 'interview_id', 'learning_plan_id', 'step_order', 'estimated_minutes']) {
    if (payload[field] === '') payload[field] = null
  }
  return payload
}

export function getLearningTasks() {
  return api.get('/learning-tasks')
}

export function bulkUpsertLearningTasks(tasks, options = {}) {
  return api.post('/learning-tasks/bulk-upsert', {
    tasks: tasks.map(taskPayload),
    replace_progress: Boolean(options.replaceProgress),
    replaceProgress: Boolean(options.replaceProgress)
  })
}

export function patchLearningTask(taskKey, patch) {
  return api.patch(`/learning-tasks/${encodeURIComponent(taskKey)}`, taskPayload(patch))
}

export function deleteLearningTask(taskKey) {
  return api.delete(`/learning-tasks/${encodeURIComponent(taskKey)}`)
}
