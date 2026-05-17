<template>
  <div>
    <div class="page-head">
      <div>
        <h1>案例标注工作台</h1>
        <p class="helper-text">
          集中维护 R1-R5 真实案例、人工评分、AI 输出核查和数据集归档信号。这里复用面试记录与评测样本标注，不新增单独案例表。
        </p>
      </div>
      <button class="btn-secondary" type="button" @click="loadCases">刷新</button>
    </div>

    <div class="stats-grid">
      <div class="card stat-card">
        <span>当前加载</span>
        <strong>{{ filteredCases.length }}</strong>
      </div>
      <div class="card stat-card">
        <span>已授权可标注</span>
        <strong>{{ authorizedCount }}</strong>
      </div>
      <div class="card stat-card">
        <span>已人工标注</span>
        <strong>{{ reviewedCount }}</strong>
      </div>
      <div class="card stat-card">
        <span>建议导出</span>
        <strong>{{ exportRecommendedCount }}</strong>
      </div>
      <div class="card stat-card">
        <span>存在幻觉</span>
        <strong>{{ hallucinationCount }}</strong>
      </div>
    </div>

    <div class="card filters-card">
      <label>状态
        <select v-model="filters.status" @change="loadCases">
          <option value="">全部</option>
          <option value="completed">已完成</option>
          <option value="in_progress">进行中</option>
        </select>
      </label>
      <label>标注
        <select v-model="filters.review_status">
          <option value="">全部</option>
          <option value="reviewed">已标注</option>
          <option value="pending">待标注</option>
        </select>
      </label>
      <label>质量
        <select v-model="filters.quality">
          <option value="">全部</option>
          <option value="high_quality">高质量</option>
          <option value="hallucination">存在幻觉</option>
          <option value="export_recommended">建议导出</option>
        </select>
      </label>
      <label>授权
        <select v-model="filters.consent">
          <option value="">全部</option>
          <option value="authorized">已授权</option>
          <option value="unauthorized">未授权</option>
        </select>
      </label>
      <label>目标岗位
        <input v-model="filters.target_position" placeholder="例如 产品助理" />
      </label>
      <label>案例编号
        <input v-model="filters.case_id" placeholder="例如 R1" />
      </label>
    </div>

    <div v-if="loading" class="card state-card">加载案例中...</div>
    <div v-else-if="errorMessage" class="card state-card error-text">
      {{ errorMessage }}
      <button class="btn-sm" type="button" @click="loadCases">重试</button>
    </div>
    <div v-else-if="filteredCases.length === 0" class="card state-card">
      <p class="empty-title">暂无符合条件的案例</p>
      <p class="helper-text">先让用户完成一次模拟面试，再到这里补 R1/R2 编号、人工评分和数据集归档判断。</p>
    </div>

    <div v-else class="card table-card">
      <table>
        <thead>
          <tr>
            <th>案例</th>
            <th>用户</th>
            <th>目标岗位</th>
            <th>AI 分</th>
            <th>人工分</th>
            <th>状态</th>
            <th>授权</th>
            <th>标注</th>
            <th>导出</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in filteredCases" :key="item.id">
            <td>
              <div class="case-id">{{ reviewOf(item).case_id || '待补' }}</div>
              <div class="case-source">{{ reviewOf(item).resume_source || `面试 #${item.id}` }}</div>
            </td>
            <td>{{ item.user_email }}</td>
            <td>{{ item.target_position || '-' }}</td>
            <td>{{ formatScore(item.overall_score) }}</td>
            <td>
              <span v-if="reviewOf(item).human_overall_score !== null && reviewOf(item).human_overall_score !== undefined">
                {{ formatScore(reviewOf(item).human_overall_score) }}
              </span>
              <span v-else class="muted">待补</span>
            </td>
            <td><span :class="['badge', item.status === 'completed' ? 'badge-green' : 'badge-yellow']">{{ item.status === 'completed' ? '已完成' : '进行中' }}</span></td>
            <td>
              <span :class="['badge', caseConsent(item) ? 'badge-green' : 'badge-blue']">
                {{ caseConsent(item) ? '已授权' : '未授权' }}
              </span>
            </td>
            <td>
              <span :class="['badge', reviewOf(item).review_status === 'reviewed' ? 'badge-green' : 'badge-yellow']">
                {{ reviewOf(item).review_status === 'reviewed' ? '已标注' : '待标注' }}
              </span>
            </td>
            <td>
              <span :class="['badge', reviewOf(item).export_recommended ? 'badge-green' : 'badge-blue']">
                {{ reviewOf(item).export_recommended ? '建议导出' : '待复核' }}
              </span>
            </td>
            <td>{{ formatDate(item.created_at) }}</td>
            <td class="row-actions">
              <button class="btn-primary btn-sm" type="button" @click="openCase(item)">快速标注</button>
              <router-link :to="`/interviews/${item.id}`" class="btn-secondary btn-sm">详情</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="drawerOpen" class="drawer-mask" @click.self="closeDrawer">
      <aside class="case-drawer">
        <div class="drawer-head">
          <div>
            <h2>案例标注 #{{ selectedCase?.id }}</h2>
            <p class="helper-text">{{ selectedCase?.target_position || '-' }} · {{ selectedCase?.user_email || '' }}</p>
          </div>
          <button class="btn-secondary" type="button" @click="closeDrawer">关闭</button>
        </div>

        <div v-if="detailLoading" class="state-card">加载详情中...</div>
        <template v-else>
          <section class="drawer-section">
            <h3>面试摘要</h3>
            <div class="summary-grid">
              <div><span>AI 综合分</span><strong>{{ formatScore(selectedDetail?.overall_score || selectedCase?.overall_score) }}</strong></div>
              <div><span>状态</span><strong>{{ selectedDetail?.status === 'completed' ? '已完成' : '进行中' }}</strong></div>
              <div><span>题数</span><strong>{{ selectedDetail?.total_questions || selectedCase?.total_questions || '-' }}</strong></div>
              <div><span>模式</span><strong>{{ interviewModeLabel(selectedDetail?.interview_mode) }}</strong></div>
              <div>
                <span>数据授权</span>
                <strong :class="selectedCaseAuthorized ? 'success-text' : 'warn-text'">
                  {{ selectedCaseReviewable ? '已授权，可人工标注' : selectedCaseAuthorized ? '无评分权限或未完成' : '未授权，不能沉淀评分' }}
                </strong>
              </div>
            </div>
            <p v-if="!selectedCaseAuthorized" class="consent-warning">
              该面试未获得本次案例去标识化数据贡献授权。可以查看详情，但不能保存人工评分或进入评测样本导出。
            </p>
          </section>

          <section class="drawer-section" v-if="selectedDetail?.report?.summary || selectedDetail?.report?.strengths?.length || selectedDetail?.report?.weaknesses?.length">
            <h3>报告核查</h3>
            <p v-if="selectedDetail?.report?.summary" class="report-summary">{{ selectedDetail.report.summary }}</p>
            <div class="report-cols">
              <div v-if="selectedDetail?.report?.strengths?.length">
                <h4>优势</h4>
                <ul><li v-for="item in selectedDetail.report.strengths" :key="item">{{ item }}</li></ul>
              </div>
              <div v-if="selectedDetail?.report?.weaknesses?.length">
                <h4>不足</h4>
                <ul><li v-for="item in selectedDetail.report.weaknesses" :key="item">{{ item }}</li></ul>
              </div>
            </div>
          </section>

          <section class="drawer-section">
            <h3>人工评分</h3>
            <div class="form-grid">
              <label>案例编号<input v-model="reviewForm.case_id" placeholder="R1" /></label>
              <label>简历来源<input v-model="reviewForm.resume_source" placeholder="例如 2590603008詹已誉简历.pdf" /></label>
              <label>数据集归档
                <select v-model="reviewForm.dataset_split">
                  <option value="">待定</option>
                  <option value="train">train</option>
                  <option value="validation">validation</option>
                  <option value="test">test</option>
                  <option value="holdout">holdout</option>
                  <option value="demo">demo</option>
                </select>
              </label>
              <label>质量等级
                <select v-model="reviewForm.quality_tier">
                  <option value="needs_review">待复核</option>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                </select>
              </label>
              <label>人工总分<input v-model.number="reviewForm.human_overall_score" type="number" min="0" max="10" step="0.5" /></label>
              <label>证据一致性<input v-model.number="reviewForm.evidence_alignment_score" type="number" min="0" max="10" step="0.5" /></label>
              <label>问题质量<input v-model.number="reviewForm.question_quality_score" type="number" min="0" max="10" step="0.5" /></label>
              <label>报告可执行性<input v-model.number="reviewForm.report_actionability_score" type="number" min="0" max="10" step="0.5" /></label>
              <label>学习任务可执行性<input v-model.number="reviewForm.learning_task_actionability_score" type="number" min="0" max="10" step="0.5" /></label>
            </div>

            <div class="check-grid">
              <label><input v-model="reviewForm.is_high_quality" type="checkbox" /> 高质量样本</label>
              <label><input v-model="reviewForm.has_hallucination" type="checkbox" /> 存在幻觉/无依据强答</label>
              <label><input v-model="reviewForm.followup_worthy" type="checkbox" /> 追问有训练价值</label>
              <label><input v-model="reviewForm.report_actionable" type="checkbox" /> 报告建议可执行</label>
            </div>

            <label class="full-field">人工评分说明
              <textarea v-model="reviewForm.human_score_notes" rows="4" placeholder="记录人工评分依据、AI 分数是否偏高/偏低、哪些结论需要复查。"></textarea>
            </label>
            <label class="full-field">复核备注
              <textarea v-model="reviewForm.notes" rows="4" placeholder="记录是否适合进入验证集、是否有可复用追问、是否存在无依据判断。"></textarea>
            </label>
          </section>

          <section class="drawer-section">
            <h3>对话片段</h3>
            <div v-if="messagePreview.length" class="message-list">
              <div v-for="msg in messagePreview" :key="msg.id" class="message-item">
                <div class="message-role">{{ msg.role === 'interviewer' ? '面试官' : '用户' }} · 第 {{ (msg.question_index ?? 0) + 1 }} 题</div>
                <p>{{ msg.content }}</p>
                <div v-if="msg.score" class="message-score">评分 {{ msg.score }}/10 {{ msg.feedback ? ` · ${msg.feedback}` : '' }}</div>
              </div>
            </div>
            <p v-else class="helper-text">暂无对话记录。</p>
          </section>

          <p v-if="noticeMessage" :class="['notice', noticeType === 'error' ? 'error-text' : 'success-text']">{{ noticeMessage }}</p>

          <div class="drawer-actions">
            <button class="btn-primary" type="button" :disabled="saving || !selectedCaseReviewable" @click="saveReview">
              {{ saving ? '保存中...' : selectedCaseReviewable ? '保存人工标注' : '不能标注' }}
            </button>
            <router-link v-if="selectedCase" :to="`/interviews/${selectedCase.id}`" class="btn-secondary">打开完整详情</router-link>
          </div>
        </template>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { interviewApi } from '../api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const cases = ref([])
const total = ref(0)
const loading = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const noticeType = ref('success')
const drawerOpen = ref(false)
const selectedCase = ref(null)
const selectedDetail = ref(null)

const filters = ref({
  status: '',
  review_status: '',
  quality: '',
  consent: '',
  target_position: '',
  case_id: ''
})

const defaultReview = () => ({
  quality_tier: 'needs_review',
  is_high_quality: false,
  has_hallucination: false,
  followup_worthy: false,
  report_actionable: false,
  notes: '',
  case_id: '',
  resume_source: '',
  human_overall_score: null,
  evidence_alignment_score: null,
  question_quality_score: null,
  report_actionability_score: null,
  learning_task_actionability_score: null,
  human_score_notes: '',
  dataset_split: ''
})

const reviewForm = ref(defaultReview())

const reviewOf = (item) => ({ ...defaultReview(), ...(item?.training_sample_review || {}) })
const caseConsent = (item) => Boolean(item?.data_contribution_consent)
const selectedCaseAuthorized = computed(() => caseConsent(selectedDetail.value || selectedCase.value))
const selectedCaseReviewable = computed(() => (
  selectedCaseAuthorized.value &&
  authStore.canReviewCases &&
  (selectedDetail.value?.status || selectedCase.value?.status) === 'completed'
))

const filteredCases = computed(() => {
  const target = filters.value.target_position.trim().toLowerCase()
  const caseId = filters.value.case_id.trim().toLowerCase()
  return cases.value.filter((item) => {
    const review = reviewOf(item)
    if (filters.value.review_status && review.review_status !== filters.value.review_status) return false
    if (filters.value.quality === 'high_quality' && !review.is_high_quality) return false
    if (filters.value.quality === 'hallucination' && !review.has_hallucination) return false
    if (filters.value.quality === 'export_recommended' && !review.export_recommended) return false
    if (filters.value.consent === 'authorized' && !caseConsent(item)) return false
    if (filters.value.consent === 'unauthorized' && caseConsent(item)) return false
    if (target && !(item.target_position || '').toLowerCase().includes(target)) return false
    if (caseId && !(review.case_id || '').toLowerCase().includes(caseId)) return false
    return true
  })
})

const authorizedCount = computed(() => filteredCases.value.filter(caseConsent).length)
const reviewedCount = computed(() => filteredCases.value.filter((item) => reviewOf(item).review_status === 'reviewed').length)
const exportRecommendedCount = computed(() => filteredCases.value.filter((item) => reviewOf(item).export_recommended).length)
const hallucinationCount = computed(() => filteredCases.value.filter((item) => reviewOf(item).has_hallucination).length)
const messagePreview = computed(() => (selectedDetail.value?.messages || []).slice(0, 6))

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function formatScore(value) {
  if (value === null || value === undefined || value === '') return '-'
  const score = Number(value)
  return Number.isFinite(score) ? score.toFixed(1) : '-'
}

function interviewModeLabel(value) {
  const labels = { single: '单面试官', panel: '多角色内评' }
  return labels[value] || value || '-'
}

function normalizePayload(form) {
  const payload = { ...form }
  for (const key of [
    'human_overall_score',
    'evidence_alignment_score',
    'question_quality_score',
    'report_actionability_score',
    'learning_task_actionability_score'
  ]) {
    if (payload[key] === '' || payload[key] === null || payload[key] === undefined) {
      payload[key] = null
    }
  }
  return payload
}

async function loadCases() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await interviewApi.list({
      page: 1,
      per_page: 100,
      status: filters.value.status || undefined
    })
    cases.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    errorMessage.value = error.message || '加载案例失败'
    cases.value = []
  } finally {
    loading.value = false
  }
}

async function openCase(item) {
  selectedCase.value = item
  selectedDetail.value = null
  reviewForm.value = reviewOf(item)
  noticeMessage.value = ''
  drawerOpen.value = true
  detailLoading.value = true
  try {
    selectedDetail.value = await interviewApi.detail(item.id)
    reviewForm.value = reviewOf(selectedDetail.value)
  } catch (error) {
    noticeType.value = 'error'
    noticeMessage.value = error.message || '加载面试详情失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  selectedCase.value = null
  selectedDetail.value = null
  noticeMessage.value = ''
}

async function saveReview() {
  if (!selectedCase.value) return
  if (!selectedCaseReviewable.value) {
    noticeType.value = 'error'
    noticeMessage.value = selectedCaseAuthorized.value
      ? '当前账号没有人工评分权限，或该面试尚未完成。'
      : '该面试未获得去标识化数据贡献授权，不能进入人工评分沉淀流程。'
    return
  }
  saving.value = true
  noticeMessage.value = ''
  try {
    const saved = await interviewApi.updateTrainingReview(selectedCase.value.id, normalizePayload(reviewForm.value))
    reviewForm.value = { ...defaultReview(), ...saved }
    if (selectedDetail.value) selectedDetail.value.training_sample_review = saved
    cases.value = cases.value.map((item) => (
      item.id === selectedCase.value.id ? { ...item, training_sample_review: saved } : item
    ))
    selectedCase.value = { ...selectedCase.value, training_sample_review: saved }
    noticeType.value = 'success'
    noticeMessage.value = '人工标注已保存'
  } catch (error) {
    noticeType.value = 'error'
    noticeMessage.value = error.message || '保存人工标注失败'
  } finally {
    saving.value = false
  }
}

onMounted(loadCases)
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}
.page-head h1 {
  font-size: 20px;
  margin-bottom: 6px;
}
.helper-text,
.muted {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.7;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-card span {
  color: #6b7280;
  font-size: 13px;
}
.stat-card strong {
  font-size: 22px;
  color: #111827;
}
.filters-card {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.filters-card label,
.form-grid label,
.full-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #374151;
  font-weight: 600;
}
.filters-card input,
.filters-card select,
.form-grid input,
.form-grid select,
.full-field textarea {
  width: 100%;
}
.state-card {
  padding: 32px;
  text-align: center;
}
.empty-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.table-card {
  overflow-x: auto;
}
.case-id {
  font-weight: 700;
  color: #111827;
}
.case-source {
  max-width: 180px;
  color: #6b7280;
  font-size: 12px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.row-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}
.btn-secondary {
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #111827;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
}
.btn-secondary:hover {
  background: #f3f4f6;
}
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.42);
  z-index: 50;
  display: flex;
  justify-content: flex-end;
}
.case-drawer {
  width: min(760px, 100vw);
  height: 100vh;
  overflow-y: auto;
  background: #f8fafc;
  padding: 24px;
  box-shadow: -8px 0 28px rgba(15, 23, 42, 0.18);
}
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.drawer-head h2 {
  font-size: 20px;
  margin-bottom: 6px;
}
.drawer-section {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 14px;
}
.drawer-section h3 {
  font-size: 16px;
  margin-bottom: 12px;
}
.summary-grid,
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.summary-grid div {
  padding: 10px;
  border-radius: 6px;
  background: #f9fafb;
}
.summary-grid span {
  display: block;
  color: #6b7280;
  font-size: 12px;
  margin-bottom: 4px;
}
.summary-grid strong {
  color: #111827;
}
.report-summary {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  margin-bottom: 12px;
}
.report-cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}
.report-cols h4 {
  margin-bottom: 6px;
  color: #111827;
}
.report-cols ul {
  padding-left: 18px;
  color: #374151;
  line-height: 1.7;
}
.check-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin: 14px 0;
}
.check-grid label {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #374151;
}
.full-field {
  margin-top: 12px;
}
.message-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.message-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #f9fafb;
}
.message-role,
.message-score {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.message-item p {
  color: #111827;
  font-size: 13px;
  line-height: 1.7;
}
.notice {
  margin: 10px 0;
  font-size: 13px;
}
.success-text {
  color: #047857;
}
.warn-text {
  color: #b45309;
}
.error-text {
  color: #dc2626;
}
.consent-warning {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  line-height: 1.7;
}
.drawer-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  padding-bottom: 24px;
}
@media (max-width: 720px) {
  .page-head,
  .drawer-head,
  .drawer-actions {
    flex-direction: column;
  }
  .case-drawer {
    width: 100vw;
    padding: 18px;
  }
}
</style>
