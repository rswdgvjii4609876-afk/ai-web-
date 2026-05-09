export const TRAINING_REVIEW_VERSION = 'training_review_v1'
export const TRAINING_REVIEW_KEY = 'zhiqizhice:training-review:v1'

function nowIso() {
  return new Date().toISOString()
}

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function textOf(value) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'object') {
    return value.summary || value.title || value.name || value.focus || value.priority || JSON.stringify(value)
  }
  return String(value)
}

export function readTrainingReviewStore() {
  const empty = {
    version: TRAINING_REVIEW_VERSION,
    records: {},
    updated_at: ''
  }
  try {
    const raw = window.localStorage.getItem(TRAINING_REVIEW_KEY)
    if (!raw) return empty
    const parsed = JSON.parse(raw)
    if (parsed?.version !== TRAINING_REVIEW_VERSION || !parsed.records || typeof parsed.records !== 'object') return empty
    return { ...empty, ...parsed }
  } catch {
    return empty
  }
}

export function readTrainingReviewRecord(interviewId) {
  const store = readTrainingReviewStore()
  return store.records?.[String(interviewId)] || {
    self_rating: '',
    notes: '',
    next_goal: '',
    updated_at: ''
  }
}

export function saveTrainingReviewRecord(interviewId, patch) {
  const key = String(interviewId || 'unknown')
  const store = readTrainingReviewStore()
  const records = {
    ...store.records,
    [key]: {
      ...readTrainingReviewRecord(key),
      ...patch,
      updated_at: nowIso()
    }
  }
  const next = {
    version: TRAINING_REVIEW_VERSION,
    records,
    updated_at: nowIso()
  }
  window.localStorage.setItem(TRAINING_REVIEW_KEY, JSON.stringify(next))
  return next.records[key]
}

export function buildTrainingReviewSummary({ report = {}, interview = {}, tasks = [] } = {}) {
  const matchingMetrics = report.matching_metrics || {}
  const abilityProfile = report.ability_gap_profile || matchingMetrics.ability_gap_profile || {}
  const gapItems = safeArray(abilityProfile.top_gaps).length
    ? abilityProfile.top_gaps
    : safeArray(abilityProfile.items)
  const commonGaps = safeArray(report.common_gaps).map(textOf)
  const weaknesses = safeArray(report.weaknesses).map(textOf)
  const trainingPriorities = safeArray(report.training_priorities).map(textOf)
  const pendingTasks = safeArray(tasks).filter(task => !task.done)
  const doneTasks = safeArray(tasks).filter(task => task.done)

  const abilityGaps = gapItems.slice(0, 5).map(item => ({
    name: item.name || item.ability_name || '待补能力',
    detail: item.evidence_basis || item.reason || `匹配度 ${item.match_score ?? '-'}`
  }))

  const nextFocus = [
    ...pendingTasks.slice(0, 3).map(task => `完成学习任务：${task.title}`),
    ...abilityGaps.slice(0, 2).map(item => `补强能力：${item.name}`),
    ...trainingPriorities.slice(0, 2)
  ].filter(Boolean).slice(0, 6)

  return {
    target_position: interview.target_position || report.target_position || '',
    overall_score: interview.overall_score || report.overall_score || '',
    strengths: safeArray(report.strengths).map(textOf).slice(0, 5),
    weaknesses: [...weaknesses, ...commonGaps].filter(Boolean).slice(0, 6),
    ability_gaps: abilityGaps,
    training_priorities: trainingPriorities.slice(0, 5),
    task_stats: {
      total: tasks.length,
      done: doneTasks.length,
      pending: pendingTasks.length
    },
    pending_tasks: pendingTasks.slice(0, 5),
    next_focus: nextFocus.length ? nextFocus : ['完成一次针对当前岗位的模拟面试，并记录复盘笔记。'],
    evidence_summary: safeArray(report.evidence_summary).map(textOf).slice(0, 5)
  }
}
