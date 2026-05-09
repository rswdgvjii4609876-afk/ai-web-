<template>
  <div class="container">
    <div class="tasks-hero card">
      <div>
        <p class="eyebrow">学习任务</p>
        <h1>把能力差距变成每天能做的事</h1>
        <p>
          报告和能力诊断中勾选的短板会汇总到这里。你可以记录完成状态、学习笔记和薄弱项变化，并用 JSON 备份或迁移进度。
        </p>
      </div>
      <div class="hero-actions">
        <router-link to="/training-review" class="btn-secondary hero-btn">训练复盘</router-link>
        <router-link to="/ability-diagnosis" class="btn-secondary hero-btn">能力诊断</router-link>
        <router-link to="/resume/upload" class="btn-primary hero-btn primary">新建面试</router-link>
      </div>
    </div>

    <div class="task-toolbar card">
      <div>
        <h2>任务库</h2>
        <p>{{ pendingCount }} 项待完成，{{ doneCount }} 项已完成</p>
      </div>
      <div class="toolbar-actions">
        <button class="btn-secondary" type="button" @click="downloadTasks" :disabled="!tasks.length">
          下载进度 JSON
        </button>
        <button class="btn-secondary" type="button" @click="triggerImport">
          上传进度 JSON
        </button>
        <button class="btn-secondary danger-outline" type="button" @click="clearTasks" :disabled="!tasks.length">
          清空本地任务
        </button>
        <input ref="fileInput" class="hidden-input" type="file" accept="application/json,.json" @change="handleImport" />
      </div>
    </div>

    <p v-if="message" :class="messageType === 'error' ? 'message error' : 'message success'">
      {{ message }}
    </p>

    <div v-if="!tasks.length" class="card empty-card">
      <h2>还没有学习任务</h2>
      <p>先上传简历生成分析，或在面试报告中把能力短板加入学习任务页。</p>
      <div class="empty-actions">
        <router-link to="/resume/upload" class="btn-primary empty-action">上传简历</router-link>
        <router-link to="/ability-diagnosis" class="btn-secondary empty-action">查看能力诊断</router-link>
        <router-link to="/training-review" class="btn-secondary empty-action">训练复盘</router-link>
      </div>
    </div>

    <div v-else class="task-list">
      <article v-for="task in tasks" :key="task.task_id" class="card task-card">
        <div class="task-head">
          <label class="task-check">
            <input type="checkbox" :checked="task.done" @change="updateTask(task.task_id, { done: $event.target.checked })" />
            <span :class="{ done: task.done }">{{ task.title }}</span>
          </label>
          <button class="remove-btn" type="button" @click="removeTask(task.task_id)">移除</button>
        </div>

        <div class="task-meta">
          <span>{{ task.target_position || '未指定岗位' }}</span>
          <span>{{ task.ability_name || '能力项' }}</span>
          <span v-if="task.priority_score !== ''">优先级 {{ task.priority_score }}</span>
          <span>来源：{{ sourceLabel(task.source_type) }}</span>
        </div>

        <div class="task-detail">
          <div>
            <strong>学习材料</strong>
            <p>{{ task.learning_material || '岗位画像知识库与学习路线' }}</p>
          </div>
          <div>
            <strong>练习任务</strong>
            <p>{{ task.practice_task || '完成一次可展示练习，并写下复盘。' }}</p>
          </div>
          <div>
            <strong>验收方式</strong>
            <ul>
              <li v-for="criterion in criteriaList(task)" :key="criterion">{{ criterion }}</li>
            </ul>
          </div>
          <div v-if="task.evidence_basis">
            <strong>来源依据</strong>
            <p>{{ task.evidence_basis }}</p>
          </div>
        </div>

        <div class="task-notes">
          <label>
            学习笔记
            <textarea
              :value="task.note"
              placeholder="记录学了什么、哪里还不熟、下一步怎么练。"
              @input="updateTask(task.task_id, { note: $event.target.value })"
            ></textarea>
          </label>
          <label>
            薄弱项变化
            <textarea
              :value="task.weak_change"
              placeholder="例如：已经完成 FastAPI 路由练习，但数据库事务还需要复习。"
              @input="updateTask(task.task_id, { weak_change: $event.target.value })"
            ></textarea>
          </label>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  LEARNING_TASKS_VERSION,
  readLearningTaskStore,
  removeLearningTask,
  updateLearningTask,
  validateLearningTaskPayload,
  writeLearningTaskStore
} from '../utils/learningTasks'

const tasks = ref([])
const fileInput = ref(null)
const message = ref('')
const messageType = ref('success')

const doneCount = computed(() => tasks.value.filter(task => task.done).length)
const pendingCount = computed(() => tasks.value.length - doneCount.value)

onMounted(() => {
  loadTasks()
  window.addEventListener('zhiqizhice-learning-tasks-updated', loadTasks)
})

onUnmounted(() => {
  window.removeEventListener('zhiqizhice-learning-tasks-updated', loadTasks)
})

function loadTasks() {
  tasks.value = readLearningTaskStore().tasks
}

function updateTask(taskId, patch) {
  updateLearningTask(taskId, patch)
  loadTasks()
}

function removeTask(taskId) {
  removeLearningTask(taskId)
  loadTasks()
  setMessage('学习任务已移除。')
}

function clearTasks() {
  if (!confirm('确定清空本浏览器里的学习任务吗？清空前建议先下载 JSON 备份。')) return
  writeLearningTaskStore({ tasks: [] })
  loadTasks()
  setMessage('本地学习任务已清空。')
}

function criteriaList(task) {
  if (Array.isArray(task.acceptance_criteria) && task.acceptance_criteria.length) return task.acceptance_criteria
  return ['完成对应练习或资料整理', '写下复盘笔记', '再次模拟面试验证表达']
}

function sourceLabel(type) {
  return {
    ability_gap: '能力差距',
    learning_plan: '学习计划',
    report_training: '报告建议',
    report_weakness: '报告短板',
    diagnosis_fallback: '诊断兜底'
  }[type] || '本地任务'
}

function downloadTasks() {
  const payload = {
    version: LEARNING_TASKS_VERSION,
    tasks: tasks.value,
    exported_at: new Date().toISOString()
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `职启智评学习任务_${Date.now()}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  setMessage('学习任务 JSON 已下载。')
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleImport(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    const payload = JSON.parse(await file.text())
    if (!validateLearningTaskPayload(payload)) {
      setMessage('上传失败：JSON 结构不符合 learning_tasks_v1。', 'error')
      return
    }
    writeLearningTaskStore(payload)
    loadTasks()
    setMessage('学习任务已导入。')
  } catch {
    setMessage('上传失败：无法解析这个 JSON 文件。', 'error')
  } finally {
    event.target.value = ''
  }
}

function setMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
}
</script>

<style scoped>
.tasks-hero {
  margin: 20px 0 18px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  border-left: 4px solid #0f766e;
}

.eyebrow {
  margin-bottom: 6px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
}

.tasks-hero h1 {
  margin-bottom: 8px;
  color: #111827;
  font-size: 26px;
}

.tasks-hero p,
.task-toolbar p,
.empty-card p,
.task-detail p,
.task-detail li {
  color: #4b5563;
  line-height: 1.7;
}

.hero-actions,
.toolbar-actions,
.empty-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-btn,
.empty-action {
  display: inline-block;
  padding: 10px 16px;
  border-radius: 8px;
}

.hero-btn.primary,
.empty-action.btn-primary {
  color: white;
}

.task-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.task-toolbar h2 {
  color: #111827;
  margin-bottom: 4px;
}

.hidden-input {
  display: none;
}

.danger-outline {
  color: #991b1b;
  background: #fee2e2;
}

.message {
  margin-bottom: 14px;
  font-size: 13px;
}

.message.success {
  color: #047857;
}

.message.error {
  color: #dc2626;
}

.empty-card {
  text-align: center;
  padding: 48px 24px;
}

.empty-card h2 {
  margin-bottom: 8px;
}

.empty-actions {
  justify-content: center;
  margin-top: 16px;
}

.task-list {
  display: grid;
  gap: 14px;
}

.task-card {
  display: grid;
  gap: 14px;
}

.task-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.task-check {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #111827;
  font-weight: 700;
}

.task-check input {
  width: auto;
}

.task-check .done {
  color: #6b7280;
  text-decoration: line-through;
}

.remove-btn {
  padding: 6px 10px;
  border-radius: 6px;
  color: #6b7280;
  background: #f3f4f6;
}

.remove-btn:hover {
  color: #991b1b;
  background: #fee2e2;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-meta span {
  padding: 4px 9px;
  border-radius: 999px;
  color: #374151;
  background: #f3f4f6;
  font-size: 12px;
  font-weight: 600;
}

.task-detail {
  display: grid;
  gap: 10px;
}

.task-detail strong {
  display: block;
  margin-bottom: 4px;
  color: #111827;
  font-size: 13px;
}

.task-detail ul {
  margin-left: 18px;
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
  min-height: 86px;
  resize: vertical;
}

@media (max-width: 760px) {
  .tasks-hero,
  .task-toolbar,
  .task-head {
    flex-direction: column;
    align-items: stretch;
  }

  .task-notes {
    grid-template-columns: 1fr;
  }
}
</style>
