<template>
  <div class="learning-plan-section">
    <div class="learning-plan-header">
      <div>
        <h4>能力提升计划</h4>
        <p>
          根据能力差距生成学习任务。导入、导出和长期进度管理请进入“学习任务”页面统一处理。
        </p>
      </div>
      <div v-if="showFileActions" class="learning-actions">
        <button class="learning-btn" type="button" @click="downloadProgress" :disabled="!tasks.length">
          下载进度
        </button>
        <button class="learning-btn" type="button" @click="triggerImport" :disabled="!tasks.length">
          上传进度
        </button>
        <input
          ref="fileInput"
          class="hidden-input"
          type="file"
          accept="application/json,.json"
          @change="handleImport"
        />
      </div>
    </div>

    <p v-if="message" :class="messageType === 'error' ? 'learning-message error' : 'learning-message success'">
      {{ message }}
    </p>

    <div class="learning-task-list">
      <article v-for="(task, index) in tasks" :key="taskKey(task, index)" class="learning-task">
        <div class="task-topline">
          <label class="task-check">
            <input
              type="checkbox"
              :checked="taskProgress(task, index).done"
              @change="updateProgress(task, index, 'done', $event.target.checked)"
            />
            <span>{{ task.title || `补强${task.ability_name || '岗位能力'}` }}</span>
          </label>
          <span class="task-priority">优先级 {{ task.priority_score ?? '-' }}</span>
        </div>

        <dl class="task-detail">
          <div>
            <dt>学习材料</dt>
            <dd>{{ task.learning_material || '岗位画像知识库' }}</dd>
          </div>
          <div>
            <dt>练习任务</dt>
            <dd>{{ task.practice_task || '整理知识点并完成一个可展示练习。' }}</dd>
          </div>
          <div>
            <dt>验收方式</dt>
            <dd>{{ acceptanceText(task) }}</dd>
          </div>
        </dl>

        <div class="task-notes">
          <label>
            学习笔记
            <textarea
              :value="taskProgress(task, index).note"
              placeholder="记录学了什么、哪里还不熟、下一步准备怎么练。"
              @input="updateProgress(task, index, 'note', $event.target.value)"
            ></textarea>
          </label>
          <label>
            薄弱项变化
            <textarea
              :value="taskProgress(task, index).weak_change"
              placeholder="例如：已完成 FastAPI 路由练习，但数据库事务还需要复习。"
              @input="updateProgress(task, index, 'weak_change', $event.target.value)"
            ></textarea>
          </label>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const VERSION = 'learning_progress_v1'

const props = defineProps({
  learningPlan: {
    type: Object,
    default: () => ({})
  },
  resumeId: {
    type: [String, Number],
    default: ''
  },
  targetPosition: {
    type: String,
    default: ''
  },
  showFileActions: {
    type: Boolean,
    default: false
  }
})

const fileInput = ref(null)
const progress = ref({})
const message = ref('')
const messageType = ref('success')

const tasks = computed(() => {
  const items = props.learningPlan?.tasks
  return Array.isArray(items) ? items : []
})

const normalizedTarget = computed(() => props.targetPosition || props.learningPlan?.target_position || 'unknown')
const storageKey = computed(() => {
  const resumePart = props.resumeId || 'unknown'
  const targetPart = String(normalizedTarget.value || 'unknown')
    .trim()
    .replace(/\s+/g, '_')
    .slice(0, 80)
  return `zhiqizhice:learning-progress:v1:${resumePart}:${targetPart}`
})

watch([tasks, storageKey], loadProgress, { immediate: true })

function taskKey(task, index) {
  return task?.task_id || `${task?.ability_id || 'task'}_${index}`
}

function createEmptyProgress() {
  return tasks.value.reduce((result, task, index) => {
    result[taskKey(task, index)] = {
      done: false,
      note: '',
      weak_change: '',
      updated_at: ''
    }
    return result
  }, {})
}

function loadProgress() {
  const empty = createEmptyProgress()
  try {
    const raw = window.localStorage.getItem(storageKey.value)
    if (!raw) {
      progress.value = empty
      return
    }
    const parsed = JSON.parse(raw)
    const savedProgress = parsed?.progress && typeof parsed.progress === 'object' ? parsed.progress : parsed
    progress.value = mergeProgress(empty, savedProgress)
  } catch {
    progress.value = empty
    setMessage('本地学习进度读取失败，已使用空进度。', 'error')
  }
}

function mergeProgress(empty, savedProgress) {
  const merged = { ...empty }
  Object.keys(merged).forEach((key) => {
    if (savedProgress?.[key] && typeof savedProgress[key] === 'object') {
      merged[key] = {
        ...merged[key],
        ...savedProgress[key]
      }
    }
  })
  return merged
}

function persistProgress() {
  window.localStorage.setItem(
    storageKey.value,
    JSON.stringify({
      version: VERSION,
      resume_id: props.resumeId,
      target_position: normalizedTarget.value,
      progress: progress.value,
      updated_at: new Date().toISOString()
    })
  )
}

function taskProgress(task, index) {
  return progress.value[taskKey(task, index)] || {
    done: false,
    note: '',
    weak_change: '',
    updated_at: ''
  }
}

function updateProgress(task, index, field, value) {
  const key = taskKey(task, index)
  progress.value = {
    ...progress.value,
    [key]: {
      ...taskProgress(task, index),
      [field]: value,
      updated_at: new Date().toISOString()
    }
  }
  persistProgress()
}

function acceptanceText(task) {
  const criteria = task?.acceptance_criteria
  if (Array.isArray(criteria) && criteria.length) return criteria.join('；')
  return task?.deliverable || '能说明学习结果，并给出可用于面试的证据。'
}

function setMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
}

function downloadProgress() {
  const payload = {
    version: VERSION,
    resume_id: props.resumeId,
    target_position: normalizedTarget.value,
    learning_plan: props.learningPlan,
    progress: progress.value,
    notes: Object.entries(progress.value).map(([taskId, value]) => ({
      task_id: taskId,
      note: value.note || '',
      weak_change: value.weak_change || '',
      done: Boolean(value.done)
    })),
    exported_at: new Date().toISOString()
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `职启智评学习进度_${props.resumeId || 'resume'}_${Date.now()}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  setMessage('学习进度 JSON 已下载。')
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleImport(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const payload = JSON.parse(text)
    if (payload?.version !== VERSION || !payload.progress || typeof payload.progress !== 'object') {
      setMessage('上传失败：JSON 版本或 progress 结构不符合 learning_progress_v1。', 'error')
      return
    }
    progress.value = mergeProgress(createEmptyProgress(), payload.progress)
    persistProgress()
    setMessage('学习进度已导入。')
  } catch {
    setMessage('上传失败：无法解析这个 JSON 文件。', 'error')
  } finally {
    event.target.value = ''
  }
}
</script>

<style scoped>
.learning-plan-section {
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.learning-plan-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.learning-plan-header h4 {
  margin: 0 0 6px;
  color: #1f2937;
}

.learning-plan-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.learning-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.learning-btn {
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #3730a3;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}

.learning-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.hidden-input {
  display: none;
}

.learning-message {
  margin: 0 0 12px;
  font-size: 13px;
}

.learning-message.success {
  color: #047857;
}

.learning-message.error {
  color: #dc2626;
}

.learning-task-list {
  display: grid;
  gap: 12px;
}

.learning-task {
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.task-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.task-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #111827;
}

.task-priority {
  color: #2563eb;
  font-size: 12px;
  white-space: nowrap;
}

.task-detail {
  display: grid;
  gap: 8px;
  margin: 12px 0;
}

.task-detail div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 10px;
}

.task-detail dt {
  color: #475569;
  font-weight: 700;
}

.task-detail dd {
  margin: 0;
  color: #334155;
  line-height: 1.6;
}

.task-notes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.task-notes label {
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.task-notes textarea {
  width: 100%;
  min-height: 76px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 9px 10px;
  resize: vertical;
  font: inherit;
  color: #111827;
}

@media (max-width: 720px) {
  .learning-plan-header,
  .task-topline {
    flex-direction: column;
    align-items: stretch;
  }

  .learning-actions {
    justify-content: flex-start;
  }

  .task-notes {
    grid-template-columns: 1fr;
  }
}
</style>
