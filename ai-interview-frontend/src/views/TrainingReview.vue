<template>
  <div class="container">
    <div class="review-hero card">
      <div>
        <p class="eyebrow">训练复盘</p>
        <h1>把学习任务、模拟面试和下一轮目标串成闭环</h1>
        <p>
          复盘记录会保存到当前账号。即使报告接口暂时失败，也可以先保存自评、复盘笔记和下一轮训练目标。
        </p>
      </div>
      <div class="hero-actions">
        <router-link to="/learning-tasks" class="btn-secondary hero-btn">学习任务</router-link>
        <router-link to="/resume/upload" class="btn-primary hero-btn primary">新建面试</router-link>
      </div>
    </div>

    <div v-if="loading" class="card loading-card">正在读取训练复盘...</div>

    <div v-else-if="!completedInterviews.length" class="card empty-card">
      <h2>还没有可复盘的已完成面试</h2>
      <p>先完成一次模拟面试，系统生成报告后，这里会汇总面试结果、学习任务和复盘笔记。</p>
      <router-link to="/resume/upload" class="btn-primary empty-action">开始一次面试</router-link>
    </div>

    <template v-else>
      <div class="card selector-card">
        <label>
          选择复盘面试
          <select v-model="selectedInterviewId">
            <option v-for="item in completedInterviews" :key="item.interview_id" :value="String(item.interview_id)">
              {{ item.target_position || '未命名岗位' }} · {{ formatDate(item.created_at) }} · 得分 {{ item.overall_score || '-' }}
            </option>
          </select>
        </label>
        <div class="selector-actions">
          <router-link v-if="selectedInterviewId" :to="`/interview/${selectedInterviewId}/report`" class="btn-secondary hero-btn">
            查看原报告
          </router-link>
          <router-link to="/learning-tasks" class="btn-secondary hero-btn">管理学习任务</router-link>
        </div>
      </div>

      <p v-if="reportError" class="error-text">{{ reportError }}</p>
      <p v-if="saveMessage" class="save-message top-save-message">{{ saveMessage }}</p>

      <CaseDataContributionCard
        v-if="selectedInterviewId"
        :consented="selectedCaseDataContributionConsent"
        :saving="caseConsentSaving"
        :message="caseConsentMessage"
        @set-consent="setSelectedCaseDataContributionConsent"
      />

      <div class="review-grid">
        <section class="card review-card">
          <p class="eyebrow">能力差距</p>
          <h2>下一轮最该补什么</h2>
          <div v-if="summary.ability_gaps.length" class="simple-list">
            <article v-for="item in summary.ability_gaps" :key="item.name" class="simple-item">
              <strong>{{ item.name }}</strong>
              <p>{{ item.detail }}</p>
            </article>
          </div>
          <p v-else class="muted-text">当前报告没有结构化能力差距，可先结合未完成学习任务和报告不足复盘。</p>
        </section>

        <section class="card review-card">
          <p class="eyebrow">学习进度</p>
          <h2>任务完成情况</h2>
          <div class="task-stats">
            <div><strong>{{ summary.task_stats.done }}</strong><span>已完成</span></div>
            <div><strong>{{ summary.task_stats.pending }}</strong><span>待完成</span></div>
            <div><strong>{{ summary.task_stats.total }}</strong><span>总任务</span></div>
          </div>
          <ul v-if="summary.pending_tasks.length" class="compact-list pending-task-list">
            <li v-for="task in summary.pending_tasks" :key="task.task_id">
              <strong>{{ task.title }}</strong>
              <span v-if="task.note">笔记：{{ task.note }}</span>
              <span v-if="task.weak_change">变化：{{ task.weak_change }}</span>
            </li>
          </ul>
          <p v-else class="muted-text">当前没有待完成学习任务，可从报告或能力诊断继续加入。</p>
        </section>

        <section class="card review-card">
          <p class="eyebrow">模拟面试</p>
          <h2>本轮结果</h2>
          <div class="score-line">
            <strong>{{ selectedInterview?.overall_score || summary.overall_score || '-' }}</strong>
            <span>{{ selectedInterview?.target_position || summary.target_position || '目标岗位' }}</span>
          </div>
          <div v-if="summary.strengths.length" class="mini-block">
            <h3>优势</h3>
            <ul class="compact-list">
              <li v-for="item in summary.strengths" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div v-if="summary.weaknesses.length" class="mini-block">
            <h3>不足</h3>
            <ul class="compact-list">
              <li v-for="item in summary.weaknesses" :key="item">{{ item }}</li>
            </ul>
          </div>
        </section>

        <section class="card review-card">
          <p class="eyebrow">下一轮训练</p>
          <h2>复盘建议</h2>
          <ul class="compact-list">
            <li v-for="item in summary.next_focus" :key="item">{{ item }}</li>
          </ul>
        </section>
      </div>

      <div class="card notes-card">
        <div>
          <p class="eyebrow">账号复盘记录</p>
          <h2>写下这轮训练结论</h2>
        </div>
        <div class="notes-grid">
          <label>
            自评分
            <select v-model="reviewForm.self_rating">
              <option value="">未填写</option>
              <option v-for="score in 10" :key="score" :value="String(score)">{{ score }} / 10</option>
            </select>
          </label>
          <label>
            下一轮目标
            <input v-model="reviewForm.next_goal" placeholder="例如：补 FastAPI + 数据库事务，再做一次产品助理面试" />
          </label>
        </div>
        <label class="note-field">
          复盘笔记
          <textarea v-model="reviewForm.notes" placeholder="记录这轮哪里进步了、哪里还卡、下一次怎么验证。"></textarea>
        </label>
        <div class="note-actions">
          <button class="btn-primary" type="button" :disabled="saving" @click="saveReview">
            {{ saving ? '保存中...' : '保存复盘' }}
          </button>
          <span v-if="saveMessage" class="save-message">{{ saveMessage }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CaseDataContributionCard from '../components/CaseDataContributionCard.vue'
import { getInterviews, getReport, updateCaseDataContributionConsent } from '../api/interview'
import { getTrainingReview, saveTrainingReview } from '../api/trainingReviews'
import { loadLearningTasksFromServer } from '../utils/learningTasks'
import { buildTrainingReviewSummary } from '../utils/trainingReview'

const route = useRoute()
const loading = ref(true)
const reportLoading = ref(false)
const reportError = ref('')
const interviews = ref([])
const selectedInterviewId = ref('')
const reportData = ref(null)
const tasks = ref([])
const reviewForm = ref(createEmptyReview())
const saveMessage = ref('')
const saving = ref(false)
const caseConsentSaving = ref(false)
const caseConsentMessage = ref('')

const completedInterviews = computed(() => {
  return interviews.value
    .filter(item => item.status === 'completed')
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
})
const selectedInterview = computed(() => {
  return completedInterviews.value.find(item => String(item.interview_id) === String(selectedInterviewId.value)) || null
})
const report = computed(() => reportData.value?.report || {})
const selectedCaseDataContributionConsent = computed(() => Boolean(
  reportData.value?.data_contribution_consent
  ?? selectedInterview.value?.data_contribution_consent
))
const summary = computed(() => buildTrainingReviewSummary({
  report: report.value,
  interview: selectedInterview.value || {},
  tasks: tasks.value
}))

onMounted(loadPage)

watch(selectedInterviewId, async (value) => {
  if (!value) return
  saveMessage.value = ''
  caseConsentMessage.value = ''
  await Promise.all([loadReport(), loadReview()])
})

async function loadPage() {
  loading.value = true
  try {
    await loadTasks()
    const data = await getInterviews()
    interviews.value = data.items || []
    const requestedId = firstQueryValue(route.query.interview_id)
    const exists = completedInterviews.value.some(item => String(item.interview_id) === String(requestedId))
    selectedInterviewId.value = exists ? String(requestedId) : String(completedInterviews.value[0]?.interview_id || '')
    if (selectedInterviewId.value) await Promise.all([loadReport(), loadReview()])
  } catch (e) {
    reportError.value = e.message || '训练复盘加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  try {
    tasks.value = (await loadLearningTasksFromServer()).tasks
  } catch (e) {
    reportError.value = e.message || '学习任务读取失败。'
    tasks.value = []
  }
}

async function loadReport() {
  if (!selectedInterviewId.value) return
  reportLoading.value = true
  reportError.value = ''
  reportData.value = null
  await loadTasks()
  try {
    reportData.value = await getReport(selectedInterviewId.value)
  } catch (e) {
    reportError.value = e.message || '报告读取失败，但仍可填写并保存复盘记录。'
  } finally {
    reportLoading.value = false
  }
}

async function loadReview() {
  if (!selectedInterviewId.value) return
  try {
    reviewForm.value = await getTrainingReview(selectedInterviewId.value)
  } catch (e) {
    reviewForm.value = createEmptyReview()
    reportError.value = e.message || '复盘记录读取失败。'
  }
}

function createEmptyReview() {
  return {
    self_rating: '',
    notes: '',
    next_goal: '',
    updated_at: ''
  }
}

function firstQueryValue(value) {
  if (Array.isArray(value)) return value[0]
  return value
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function saveReview() {
  if (!selectedInterviewId.value) return
  saving.value = true
  try {
    reviewForm.value = await saveTrainingReview(selectedInterviewId.value, reviewForm.value)
    saveMessage.value = '复盘记录已保存到账号。'
  } catch (e) {
    saveMessage.value = e.message || '复盘记录保存失败。'
  } finally {
    saving.value = false
  }
}

async function setSelectedCaseDataContributionConsent(consent) {
  if (!selectedInterviewId.value) return
  caseConsentSaving.value = true
  caseConsentMessage.value = ''
  try {
    const result = await updateCaseDataContributionConsent(selectedInterviewId.value, consent)
    const nextConsent = Boolean(result.data_contribution_consent)
    reportData.value = {
      ...(reportData.value || {}),
      data_contribution_consent: nextConsent,
      privacy_consent_snapshot: result.privacy_consent_snapshot
    }
    interviews.value = interviews.value.map(item => (
      String(item.interview_id) === String(selectedInterviewId.value)
        ? { ...item, data_contribution_consent: nextConsent }
        : item
    ))
    caseConsentMessage.value = consent
      ? '已记录本次案例授权，可进入后台人工评分和去标识化评测数据沉淀。'
      : '已撤回本次案例的数据贡献授权，后续导出和人工评分沉淀会跳过该案例。'
  } catch (e) {
    caseConsentMessage.value = e.message || '更新本次案例授权失败，请稍后重试。'
  } finally {
    caseConsentSaving.value = false
  }
}
</script>

<style scoped>
.review-hero {
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

.review-hero h1,
.review-card h2,
.notes-card h2,
.empty-card h2 {
  margin-bottom: 8px;
  color: #111827;
}

.review-hero h1 {
  font-size: 26px;
}

.review-hero p,
.muted-text,
.empty-card p,
.simple-item p,
.compact-list li {
  color: #4b5563;
  line-height: 1.7;
}

.hero-actions,
.selector-actions,
.note-actions {
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
.empty-action {
  color: white;
}

.loading-card,
.empty-card {
  text-align: center;
  padding: 48px 24px;
}

.empty-action {
  margin-top: 16px;
}

.selector-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-end;
  margin-bottom: 16px;
}

.selector-card label {
  flex: 1;
  display: grid;
  gap: 8px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

.error-text {
  margin-bottom: 16px;
  color: #dc2626;
  font-size: 13px;
}

.review-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.review-card {
  display: grid;
  gap: 12px;
}

.simple-list {
  display: grid;
  gap: 10px;
}

.simple-item {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.simple-item strong {
  color: #111827;
}

.task-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.task-stats div {
  padding: 12px;
  border-radius: 8px;
  background: #f9fafb;
  text-align: center;
}

.task-stats strong {
  display: block;
  color: #111827;
  font-size: 24px;
}

.task-stats span {
  color: #6b7280;
  font-size: 12px;
}

.compact-list {
  margin-left: 18px;
}

.pending-task-list li {
  margin-bottom: 8px;
}

.pending-task-list strong,
.pending-task-list span {
  display: block;
}

.pending-task-list span {
  color: #6b7280;
  font-size: 12px;
}

.score-line {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.score-line strong {
  color: #111827;
  font-size: 32px;
}

.score-line span {
  color: #6b7280;
}

.mini-block h3 {
  margin: 8px 0 6px;
  color: #111827;
  font-size: 14px;
}

.notes-card {
  display: grid;
  gap: 14px;
  margin-bottom: 24px;
}

.notes-grid {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 12px;
}

.notes-grid label,
.note-field {
  display: grid;
  gap: 6px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

.note-field textarea {
  min-height: 120px;
  resize: vertical;
}

.save-message {
  color: #047857;
  font-size: 13px;
  align-self: center;
}

.top-save-message {
  margin-bottom: 12px;
}

@media (max-width: 760px) {
  .review-hero,
  .selector-card {
    flex-direction: column;
    align-items: stretch;
  }

  .review-grid,
  .notes-grid {
    grid-template-columns: 1fr;
  }
}
</style>
