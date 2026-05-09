<template>
  <div class="container">
    <div class="diagnosis-hero card">
      <div>
        <p class="eyebrow">能力诊断</p>
        <h1>从岗位差距到学习计划</h1>
        <p>
          这里把最近一次简历分析整理成个人能力画像：先看岗位匹配与短板，再按学习任务补证据，最后回到模拟面试训练。
        </p>
      </div>
      <div class="hero-actions">
        <router-link to="/resume/upload" class="btn-primary hero-btn primary">新建面试</router-link>
        <router-link to="/dashboard" class="btn-secondary hero-btn">返回工作台</router-link>
      </div>
    </div>

    <div v-if="loading" class="card loading-card">正在读取能力诊断...</div>

    <div v-else-if="error" class="card empty-card">
      <h2>暂时无法生成能力诊断</h2>
      <p>{{ error }}</p>
      <router-link to="/resume/upload" class="btn-primary empty-action">上传简历并生成诊断</router-link>
    </div>

    <template v-else-if="resume">
      <div class="summary-grid">
        <div class="card summary-card">
          <span>目标岗位</span>
          <strong>{{ targetPosition || '未填写' }}</strong>
          <small>{{ resume.file_name || '简历文件' }}</small>
        </div>
        <div class="card summary-card">
          <span>岗位匹配分</span>
          <strong>{{ scoreText(matchingMetrics?.final_score) }}</strong>
          <small>{{ semanticSourceLabel(matchingMetrics) }}</small>
        </div>
        <div class="card summary-card">
          <span>能力匹配度</span>
          <strong>{{ scoreText(abilityProfile?.overall_match_score) }}</strong>
          <small>{{ abilityProfile?.matched_profile?.job_name || targetPosition || '岗位能力图谱' }}</small>
        </div>
      </div>

      <div class="diagnosis-grid">
        <section class="card section-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">能力差距</p>
              <h2>优先补强的能力</h2>
            </div>
            <span class="section-badge">{{ topGaps.length }} 项重点</span>
          </div>
          <div v-if="topGaps.length" class="gap-list">
            <article v-for="item in topGaps" :key="item.ability_id || item.name" class="gap-item">
              <div class="gap-title">
                <strong>{{ item.name }}</strong>
                <span>优先级 {{ item.priority_score ?? '-' }}</span>
              </div>
              <div class="level-line">
                <span>当前 {{ item.current_level }} / 要求 {{ item.required_level }}</span>
                <span>匹配 {{ scoreText(item.match_score) }}</span>
              </div>
              <div class="level-bar">
                <div class="level-bar-fill" :style="{ width: `${safePercent(item.match_score)}%` }"></div>
              </div>
              <p>{{ item.evidence_basis || '需要继续补充可验证经历或作品证据。' }}</p>
              <div v-if="item.missing_keywords?.length" class="tag-list">
                <span v-for="keyword in item.missing_keywords.slice(0, 6)" :key="keyword" class="tag tag-missing">
                  {{ keyword }}
                </span>
              </div>
            </article>
          </div>
          <p v-else class="muted-text">当前简历没有明显能力差距，建议继续通过模拟面试验证表达和证据完整度。</p>
        </section>

        <section class="card section-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">已有证据</p>
              <h2>简历能支持什么结论</h2>
            </div>
          </div>
          <div v-if="evidenceItems.length" class="evidence-list">
            <p v-for="item in evidenceItems" :key="item">{{ item }}</p>
          </div>
          <p v-else class="muted-text">暂未读取到明确证据摘要，可回到简历分析页查看原始解析内容。</p>
          <div v-if="strengths.length" class="strength-block">
            <h3>相对优势</h3>
            <div class="tag-list">
              <span v-for="item in strengths" :key="item.ability_id || item.name" class="tag tag-strength">
                {{ item.name }} {{ scoreText(item.match_score) }}
              </span>
            </div>
          </div>
        </section>
      </div>

      <LearningPlanProgress
        v-if="learningPlanTasks.length"
        class="diagnosis-learning"
        :learning-plan="learningPlan"
        :resume-id="resume.resume_id"
        :target-position="targetPosition"
      />

      <div v-else class="card empty-card">
        <h2>暂无学习计划</h2>
        <p>这份简历暂时没有生成可执行学习任务，可以重新上传简历或等待后续报告链路补全学习计划。</p>
      </div>

      <div class="card training-card">
        <div>
          <h2>下一步训练</h2>
          <p>围绕当前岗位重新上传或更新简历，系统会继续按岗位画像、简历证据和能力差距生成面试追问。</p>
        </div>
        <router-link :to="resumeUploadLink" class="btn-primary hero-btn primary">围绕该岗位训练</router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getResume, getResumes } from '../api/resume'
import LearningPlanProgress from '../components/LearningPlanProgress.vue'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const resume = ref(null)

const analysis = computed(() => resume.value?.analysis || {})
const matchingMetrics = computed(() => analysis.value?.matching_metrics || null)
const abilityProfile = computed(() => analysis.value?.ability_gap_profile || matchingMetrics.value?.ability_gap_profile || null)
const learningPlan = computed(() => analysis.value?.learning_plan || matchingMetrics.value?.learning_plan || null)
const learningPlanTasks = computed(() => {
  const tasks = learningPlan.value?.tasks
  return Array.isArray(tasks) ? tasks : []
})
const targetPosition = computed(() => resume.value?.target_position || abilityProfile.value?.target_position || learningPlan.value?.target_position || '')
const topGaps = computed(() => {
  const profile = abilityProfile.value || {}
  const items = Array.isArray(profile.top_gaps) && profile.top_gaps.length ? profile.top_gaps : profile.items
  return Array.isArray(items) ? items.slice(0, 5) : []
})
const strengths = computed(() => {
  const items = abilityProfile.value?.strengths
  return Array.isArray(items) ? items.slice(0, 4) : []
})
const evidenceItems = computed(() => {
  const direct = resume.value?.evidence_summary
  if (Array.isArray(direct) && direct.length) return direct.slice(0, 6)
  const basis = matchingMetrics.value?.evidence_basis
  if (Array.isArray(basis) && basis.length) return basis.slice(0, 6)
  const summary = analysis.value?.summary
  return summary ? [summary] : []
})
const resumeUploadLink = computed(() => ({
  path: '/resume/upload',
  query: targetPosition.value ? { target_position: targetPosition.value } : {}
}))

onMounted(loadDiagnosis)

async function loadDiagnosis() {
  loading.value = true
  error.value = ''
  try {
    const requestedId = firstQueryValue(route.query.resume_id)
    const resumeId = requestedId || await findLatestCompletedResumeId()
    if (!resumeId) {
      error.value = '还没有已完成的简历分析。请先上传简历，生成岗位匹配和能力差距结果。'
      return
    }
    const detail = await getResume(resumeId)
    if (detail?.status && detail.status !== 'completed') {
      error.value = `这份简历当前状态为 ${detail.status}，需要分析完成后才能查看能力诊断。`
      return
    }
    resume.value = detail
    if (!analysis.value || !Object.keys(analysis.value).length) {
      error.value = '这份简历没有可用的分析结果，请重新上传或稍后再试。'
    }
  } catch (e) {
    error.value = e.message || '能力诊断加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function firstQueryValue(value) {
  if (Array.isArray(value)) return value[0]
  return value
}

async function findLatestCompletedResumeId() {
  const data = await getResumes()
  const items = Array.isArray(data) ? data : data?.items || []
  const completed = items
    .filter(item => item.status === 'completed')
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
  return completed[0]?.resume_id || null
}

function scoreText(value) {
  if (typeof value !== 'number') return '-'
  return `${Math.round(value)}`
}

function safePercent(value) {
  const num = typeof value === 'number' ? value : 0
  return Math.max(0, Math.min(100, Math.round(num)))
}

function semanticSourceLabel(metrics) {
  if (!metrics) return '等待匹配指标'
  if (metrics.semantic_backend === 'deepseek_embedding') return 'DeepSeek embedding'
  if (metrics.semantic_backend === 'openai_embedding') return 'OpenAI embedding'
  if (String(metrics.embedding_status || '').startsWith('fallback')) return 'TF-IDF 回退'
  return 'TF-IDF'
}
</script>

<style scoped>
.diagnosis-hero {
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

.diagnosis-hero h1,
.section-card h2,
.training-card h2,
.empty-card h2 {
  margin-bottom: 8px;
  color: #111827;
}

.diagnosis-hero h1 {
  font-size: 26px;
}

.diagnosis-hero p,
.training-card p,
.empty-card p,
.muted-text {
  color: #4b5563;
  line-height: 1.8;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  display: grid;
  gap: 8px;
}

.summary-card span,
.summary-card small {
  color: #64748b;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 24px;
}

.diagnosis-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr);
  gap: 16px;
  align-items: start;
}

.section-card,
.diagnosis-learning,
.training-card {
  margin-bottom: 16px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.section-badge {
  padding: 4px 10px;
  border-radius: 999px;
  color: #1d4ed8;
  background: #dbeafe;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.gap-list,
.evidence-list {
  display: grid;
  gap: 10px;
}

.gap-item {
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.gap-title,
.level-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.gap-title strong {
  color: #111827;
}

.gap-title span,
.level-line {
  color: #64748b;
  font-size: 12px;
}

.level-bar {
  height: 7px;
  margin: 8px 0;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.level-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e, #4f46e5);
}

.gap-item p {
  margin: 8px 0 0;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.7;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.tag-missing {
  color: #92400e;
  background: #fef3c7;
}

.tag-strength {
  color: #065f46;
  background: #d1fae5;
}

.evidence-list p {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f9fafb;
  color: #374151;
  font-size: 13px;
  line-height: 1.7;
}

.strength-block {
  margin-top: 16px;
}

.strength-block h3 {
  margin-bottom: 8px;
  color: #111827;
  font-size: 15px;
}

.training-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

@media (max-width: 760px) {
  .diagnosis-hero,
  .training-card,
  .section-head,
  .gap-title,
  .level-line {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    flex-direction: column;
  }

  .summary-grid,
  .diagnosis-grid {
    grid-template-columns: 1fr;
  }
}
</style>
