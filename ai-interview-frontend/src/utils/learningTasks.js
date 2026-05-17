import {
  bulkUpsertLearningTasks,
  deleteLearningTask,
  getLearningTasks,
  patchLearningTask
} from '../api/learningTasks'

export const LEARNING_TASKS_VERSION = 'learning_tasks_v1'
export const LEARNING_TASKS_KEY = 'zhiqizhice:learning-tasks:v1'

function nowIso() {
  return new Date().toISOString()
}

function safeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (typeof value === 'object') {
    return value.summary || value.title || value.name || value.focus || JSON.stringify(value)
  }
  return fallback
}

function compactId(value) {
  return safeText(value, 'task')
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u4e00-\u9fa5-]/g, '')
    .slice(0, 96) || 'task'
}

function safeNumber(value, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

export function readLearningTaskStore() {
  const empty = {
    version: LEARNING_TASKS_VERSION,
    tasks: [],
    updated_at: ''
  }
  try {
    const raw = window.localStorage.getItem(LEARNING_TASKS_KEY)
    if (!raw) return empty
    const parsed = JSON.parse(raw)
    if (parsed?.version !== LEARNING_TASKS_VERSION || !Array.isArray(parsed.tasks)) return empty
    return {
      ...empty,
      ...parsed,
      tasks: parsed.tasks.map(normalizeLearningTask).filter(Boolean)
    }
  } catch {
    return empty
  }
}

export function writeLearningTaskStore(payload) {
  const store = {
    version: LEARNING_TASKS_VERSION,
    tasks: Array.isArray(payload?.tasks) ? payload.tasks.map(normalizeLearningTask).filter(Boolean) : [],
    updated_at: nowIso()
  }
  window.localStorage.setItem(LEARNING_TASKS_KEY, JSON.stringify(store))
  window.dispatchEvent(new CustomEvent('zhiqizhice-learning-tasks-updated', { detail: store }))
  return store
}

export function normalizeLearningTask(input) {
  if (!input) return null
  const abilityName = safeText(input.ability_name || input.name || input.ability_id || input.title, '待提升能力')
  const title = safeText(input.title, `补强：${abilityName}`)
  const targetPosition = safeText(input.target_position || input.targetPosition, '未指定岗位')
  const sourceType = safeText(input.source_type || input.sourceType, 'manual')
  const sourceId = safeText(input.source_id || input.sourceId || input.resume_id || input.interview_id, 'local')
  const taskId = safeText(input.task_id || input.id) || [
    sourceType,
    sourceId,
    targetPosition,
    abilityName,
    title
  ].map(compactId).join('__')

  return {
    task_id: taskId,
    title,
    ability_name: abilityName,
    target_position: targetPosition,
    source_type: sourceType,
    source_id: sourceId,
    resume_id: input.resume_id || '',
    interview_id: input.interview_id || '',
    priority_score: input.priority_score ?? input.priority ?? '',
    route_source: safeText(input.route_source || input.routeSource, ''),
    route_stage: safeText(input.route_stage || input.routeStage, ''),
    task_type: safeText(input.task_type || input.taskType || input.material_type, ''),
    estimated_minutes: safeNumber(input.estimated_minutes || input.estimatedMinutes, ''),
    due_date: safeText(input.due_date || input.dueDate, ''),
    learning_material: safeText(input.learning_material || input.material, '岗位画像知识库与相关学习路线'),
    practice_task: safeText(input.practice_task || input.practice, '整理知识点并完成一个可展示练习。'),
    acceptance_criteria: Array.isArray(input.acceptance_criteria)
      ? input.acceptance_criteria
      : [safeText(input.acceptance_criteria || input.acceptance || input.deliverable, '能说明学习结果，并给出可用于面试的证据。')],
    evidence_basis: safeText(input.evidence_basis || input.evidence || input.reason, ''),
    quality_level: safeText(input.quality_level || input.qualityLevel, ''),
    quality_label: safeText(input.quality_label || input.qualityLabel, ''),
    quality_issues: Array.isArray(input.quality_issues)
      ? input.quality_issues.map(item => safeText(item)).filter(Boolean)
      : [],
    task_metadata: input.task_metadata && typeof input.task_metadata === 'object'
      ? input.task_metadata
      : (input.taskMetadata && typeof input.taskMetadata === 'object' ? input.taskMetadata : {}),
    done: Boolean(input.done),
    note: safeText(input.note, ''),
    weak_change: safeText(input.weak_change, ''),
    created_at: input.created_at || nowIso(),
    updated_at: input.updated_at || nowIso()
  }
}

export function upsertLearningTask(input) {
  const task = normalizeLearningTask(input)
  if (!task) return readLearningTaskStore()
  const store = readLearningTaskStore()
  const index = store.tasks.findIndex(item => item.task_id === task.task_id)
  const tasks = [...store.tasks]
  if (index >= 0) {
    tasks[index] = {
      ...tasks[index],
      ...task,
      done: tasks[index].done,
      note: tasks[index].note,
      weak_change: tasks[index].weak_change,
      created_at: tasks[index].created_at,
      updated_at: nowIso()
    }
  } else {
    tasks.unshift(task)
  }
  return writeLearningTaskStore({ tasks })
}

export async function loadLearningTasksFromServer() {
  const data = await getLearningTasks()
  const tasks = Array.isArray(data?.tasks) ? data.tasks : (Array.isArray(data?.items) ? data.items : [])
  return {
    version: LEARNING_TASKS_VERSION,
    tasks: tasks.map(normalizeLearningTask).filter(Boolean),
    updated_at: data?.updated_at || ''
  }
}

export async function upsertLearningTasksToServer(items, options = {}) {
  const tasks = Array.isArray(items) ? items.map(normalizeLearningTask).filter(Boolean) : []
  if (!tasks.length) return loadLearningTasksFromServer()
  const data = await bulkUpsertLearningTasks(tasks, options)
  const returnedTasks = Array.isArray(data?.tasks) ? data.tasks : (Array.isArray(data?.items) ? data.items : tasks)
  return {
    version: LEARNING_TASKS_VERSION,
    tasks: returnedTasks.map(normalizeLearningTask).filter(Boolean),
    updated_at: new Date().toISOString()
  }
}

export async function upsertLearningTaskToServer(input) {
  return upsertLearningTasksToServer([input])
}

export function upsertLearningTasks(items) {
  const incoming = Array.isArray(items) ? items.map(normalizeLearningTask).filter(Boolean) : []
  if (!incoming.length) return readLearningTaskStore()
  const store = readLearningTaskStore()
  const tasks = [...store.tasks]
  incoming.forEach((task) => {
    const index = tasks.findIndex(item => item.task_id === task.task_id)
    if (index >= 0) {
      tasks[index] = {
        ...tasks[index],
        ...task,
        done: tasks[index].done,
        note: tasks[index].note,
        weak_change: tasks[index].weak_change,
        created_at: tasks[index].created_at,
        updated_at: nowIso()
      }
    } else {
      tasks.unshift(task)
    }
  })
  return writeLearningTaskStore({ tasks })
}

export function updateLearningTask(taskId, patch) {
  const store = readLearningTaskStore()
  const tasks = store.tasks.map(task => (
    task.task_id === taskId ? { ...task, ...patch, updated_at: nowIso() } : task
  ))
  return writeLearningTaskStore({ tasks })
}

export async function updateLearningTaskOnServer(taskId, patch) {
  const data = await patchLearningTask(taskId, patch)
  return normalizeLearningTask(data)
}

export function removeLearningTask(taskId) {
  const store = readLearningTaskStore()
  return writeLearningTaskStore({ tasks: store.tasks.filter(task => task.task_id !== taskId) })
}

export async function removeLearningTaskFromServer(taskId) {
  await deleteLearningTask(taskId)
  return true
}

export async function migrateLocalLearningTasksToServer() {
  const store = readLearningTaskStore()
  if (!store.tasks.length) return { ...store, migrated: 0 }
  const result = await upsertLearningTasksToServer(store.tasks, { replaceProgress: true })
  return { ...result, migrated: store.tasks.length }
}

export function validateLearningTaskPayload(payload) {
  return payload?.version === LEARNING_TASKS_VERSION && Array.isArray(payload.tasks)
}

export function taskFromAbilityGap(item, context = {}) {
  const abilityName = safeText(item?.name || item?.ability_name || item?.ability_id, '岗位能力')
  const missingKeywords = Array.isArray(item?.missing_keywords) ? item.missing_keywords.join('、') : ''
  return normalizeLearningTask({
    title: `补强：${abilityName}`,
    ability_name: abilityName,
    target_position: context.target_position,
    source_type: context.source_type || 'ability_gap',
    source_id: context.source_id || context.resume_id || context.interview_id,
    resume_id: context.resume_id,
    interview_id: context.interview_id,
    priority_score: item?.priority_score,
    route_source: item?.route_source,
    route_stage: item?.route_stage,
    task_type: item?.task_type,
    estimated_minutes: item?.estimated_minutes,
    task_metadata: item?.task_metadata,
    learning_material: missingKeywords ? `优先复习：${missingKeywords}` : '岗位画像知识库、学习路线和项目复盘材料',
    practice_task: `围绕“${abilityName}”完成一次知识梳理，并补充一个能放进简历或面试表达的例子。`,
    acceptance_criteria: [
      '能用自己的话讲清核心概念',
      '能给出项目或练习证据',
      '能在模拟面试中回答一轮追问'
    ],
    evidence_basis: item?.evidence_basis || item?.reason || ''
  })
}

export function taskFromText(text, context = {}) {
  const content = safeText(text)
  if (!content) return null
  return normalizeLearningTask({
    title: content.length > 28 ? `${content.slice(0, 28)}...` : content,
    ability_name: context.ability_name || '报告建议',
    target_position: context.target_position,
    source_type: context.source_type || 'report_advice',
    source_id: context.source_id || content,
    resume_id: context.resume_id,
    interview_id: context.interview_id,
    priority_score: context.priority_score || '',
    route_source: context.route_source || '',
    route_stage: context.route_stage || '',
    task_type: context.task_type || '',
    estimated_minutes: context.estimated_minutes || '',
    task_metadata: context.task_metadata || {},
    learning_material: '报告建议、岗位画像知识库和个人复盘记录',
    practice_task: content,
    acceptance_criteria: ['完成对应练习或资料整理', '写下复盘笔记', '再次模拟面试验证表达'],
    evidence_basis: content
  })
}

export function taskFromLearningPlan(task, context = {}) {
  return normalizeLearningTask({
    ...task,
    target_position: context.target_position || task?.target_position,
    source_type: context.source_type || 'learning_plan',
    source_id: context.source_id || context.resume_id || context.interview_id,
    resume_id: context.resume_id,
    interview_id: context.interview_id
  })
}
