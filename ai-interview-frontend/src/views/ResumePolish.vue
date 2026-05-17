<template>
  <div class="container polish-page">
    <section class="card polish-hero">
      <div>
        <p class="eyebrow">简历润色</p>
        <h1>按岗位评分逻辑润色简历</h1>
        <p>
          上传 PDF 后，系统会先完成简历解析、岗位匹配评分和能力差距分析，再调用你的大模型 API
          生成证据约束下的润色建议。润色只改表达和结构，不替你编造经历。
        </p>
      </div>
      <div class="hero-links">
        <router-link class="btn-secondary" to="/ability-diagnosis">能力诊断</router-link>
        <router-link class="btn-secondary" to="/learning-tasks">学习任务</router-link>
      </div>
    </section>

    <section class="card upload-card">
      <div class="form-grid">
        <label>
          目标岗位
          <input v-model="targetPosition" placeholder="例如：Python后端开发工程师 / 产品助理" />
        </label>
        <label>
          润色模式
          <select v-model="polishMode">
            <option value="job_aligned">岗位强化</option>
            <option value="conservative">保守润色</option>
            <option value="ats_keywords">关键词对齐</option>
          </select>
        </label>
        <label class="full">
          补充说明
          <textarea
            v-model="userNotes"
            rows="3"
            placeholder="可补充真实经历边界、目标企业、希望突出或避免的内容。不要写入虚假经历。"
          ></textarea>
        </label>
        <label class="full file-input">
          上传 PDF 简历
          <input type="file" accept="application/pdf" @change="handleFileChange" />
          <span>{{ selectedFile?.name || '仅支持 10MB 内 PDF' }}</span>
        </label>
      </div>
      <div class="actions">
        <button class="btn-primary" type="button" :disabled="isRunning" @click="runPolish">
          {{ isRunning ? currentStep : '开始评分并润色' }}
        </button>
        <button class="btn-secondary" type="button" :disabled="isRunning" @click="resetPage">清空</button>
      </div>
      <p v-if="error" class="error-text">{{ error }}</p>
    </section>

    <section v-if="currentResume" class="summary-grid">
      <div class="card summary-card">
        <span>解析状态</span>
        <strong>{{ currentResume.status }}</strong>
        <small>{{ currentResume.file_name }}</small>
      </div>
      <div class="card summary-card">
        <span>岗位匹配分</span>
        <strong>{{ scoreText(matchingMetrics?.final_score) }}</strong>
        <small>{{ currentResume.target_position }}</small>
      </div>
      <div class="card summary-card">
        <span>能力匹配度</span>
        <strong>{{ scoreText(abilityProfile?.overall_match_score) }}</strong>
        <small>按岗位能力图谱计算</small>
      </div>
    </section>

    <section v-if="polishResult" class="result-grid">
      <div class="card section-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">评分依据</p>
            <h2>先看问题，再改表达</h2>
          </div>
          <span class="badge">{{ polishResult.polish_mode }}</span>
        </div>
        <p class="strategy">{{ polishResult.overall_strategy }}</p>
        <div class="warning-list">
          <strong>证据约束</strong>
          <p v-for="item in polishResult.risk_warnings || []" :key="item">{{ item }}</p>
        </div>
        <div v-if="knowledgeSources.length" class="tag-block">
          <strong>本次参考的岗位资料</strong>
          <span v-for="item in knowledgeSources" :key="item.title" class="tag">
            {{ item.title }}{{ item.is_member_submission ? '（成员补充）' : '' }}
          </span>
          <p class="source-note">
            岗位资料只用于对齐岗位要求和表达重点，不会被写成你的真实经历。
          </p>
        </div>
        <div v-if="missingEvidence.length" class="tag-block">
          <strong>建议补充的真实证据</strong>
          <span v-for="item in missingEvidence" :key="item" class="tag">{{ item }}</span>
        </div>
      </div>

      <div class="card section-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">分段建议</p>
            <h2>可逐条检查后采用</h2>
          </div>
        </div>
        <article v-for="item in suggestions" :key="`${item.section}-${item.issue}`" class="suggestion-card">
          <div class="suggestion-head">
            <strong>{{ item.section }}</strong>
            <span :class="['risk', `risk-${item.risk_level || 'medium'}`]">{{ riskLabel(item.risk_level) }}</span>
          </div>
          <p v-if="item.issue"><b>问题：</b>{{ item.issue }}</p>
          <p v-if="item.evidence_basis"><b>依据：</b>{{ item.evidence_basis }}</p>
          <p v-if="item.rewrite_strategy"><b>策略：</b>{{ item.rewrite_strategy }}</p>
          <pre v-if="item.rewritten_text">{{ item.rewritten_text }}</pre>
          <p v-if="item.risk_note" class="risk-note">{{ item.risk_note }}</p>
        </article>
      </div>

      <div class="card markdown-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">润色稿</p>
            <h2>复制后人工确认再使用</h2>
          </div>
          <button class="btn-secondary" type="button" @click="copyMarkdown">复制 Markdown</button>
        </div>
        <textarea v-model="editableMarkdown" rows="18"></textarea>
        <div class="actions">
          <router-link
            v-if="resumeId"
            class="btn-secondary"
            :to="`/ability-diagnosis?resume_id=${resumeId}`"
          >
            查看能力诊断
          </router-link>
          <router-link class="btn-primary" to="/resume/upload">进入模拟面试</router-link>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getResume, polishResume, uploadResume } from '../api/resume'
import { normalizeResumeEvaluation } from '../utils/resumeEvaluation'

const selectedFile = ref(null)
const targetPosition = ref('Python后端开发工程师')
const polishMode = ref('job_aligned')
const userNotes = ref('')
const currentResume = ref(null)
const polishResult = ref(null)
const editableMarkdown = ref('')
const resumeId = ref(null)
const isRunning = ref(false)
const currentStep = ref('')
const error = ref('')
const privacyBaseAgreed = ref(true)
const dataContributionConsent = ref(true)

const analysis = computed(() => currentResume.value?.analysis || {})
const resumeEvaluation = computed(() => normalizeResumeEvaluation(analysis.value || {}))
const matchingMetrics = computed(() => resumeEvaluation.value.matchingMetrics || null)
const abilityProfile = computed(() => resumeEvaluation.value.abilityProfile || null)
const suggestions = computed(() => polishResult.value?.section_suggestions || [])
const missingEvidence = computed(() => polishResult.value?.missing_evidence_to_prepare || [])
const knowledgeSources = computed(() => polishResult.value?.knowledge_sources || [])

watch(polishResult, value => {
  editableMarkdown.value = value?.polished_resume_markdown || ''
})

function handleFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null
}

function scoreText(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${Math.round(number)}`
}

function riskLabel(value) {
  if (value === 'high') return '高风险'
  if (value === 'low') return '低风险'
  return '中风险'
}

function resetPage() {
  selectedFile.value = null
  currentResume.value = null
  polishResult.value = null
  editableMarkdown.value = ''
  resumeId.value = null
  error.value = ''
}

async function waitForResumeCompleted(id) {
  for (let index = 0; index < 60; index += 1) {
    const detail = await getResume(id)
    currentResume.value = detail
    if (detail.status === 'completed') return detail
    if (detail.status === 'failed') {
      throw new Error(detail.error_message || '简历分析失败，请检查 PDF 内容或 API 配置')
    }
    await new Promise(resolve => setTimeout(resolve, 2500))
  }
  throw new Error('简历分析等待超时，请稍后在能力诊断页查看结果')
}

async function runPolish() {
  error.value = ''
  polishResult.value = null
  editableMarkdown.value = ''
  if (!selectedFile.value) {
    error.value = '请先选择 PDF 简历'
    return
  }
  if (!targetPosition.value.trim()) {
    error.value = '请填写目标岗位'
    return
  }
  if (!privacyBaseAgreed.value) {
    error.value = '请先阅读并同意《隐私协议与个人信息处理说明》'
    return
  }
  isRunning.value = true
  try {
    currentStep.value = '上传并解析中...'
    const upload = await uploadResume(selectedFile.value, targetPosition.value.trim(), {
      privacyAgreed: privacyBaseAgreed.value,
      dataContributionConsent: dataContributionConsent.value
    })
    resumeId.value = upload.resume_id
    currentStep.value = '等待评分完成...'
    await waitForResumeCompleted(upload.resume_id)
    currentStep.value = '生成润色建议...'
    polishResult.value = await polishResume(upload.resume_id, {
      polish_mode: polishMode.value,
      target_position: targetPosition.value.trim(),
      user_notes: userNotes.value.trim()
    })
    currentStep.value = '完成'
  } catch (err) {
    error.value = err.message || '简历润色失败，请稍后重试'
  } finally {
    isRunning.value = false
  }
}

async function copyMarkdown() {
  if (!editableMarkdown.value) return
  await navigator.clipboard.writeText(editableMarkdown.value)
}
</script>

<style scoped>
.polish-page {
  padding-bottom: 48px;
}
.polish-hero,
.upload-card,
.markdown-card {
  margin-bottom: 18px;
}
.polish-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}
.polish-hero h1 {
  margin: 8px 0;
  font-size: 30px;
}
.polish-hero p,
.strategy {
  color: #4b5563;
  line-height: 1.7;
}
.hero-links,
.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-weight: 600;
}
.form-grid .full {
  grid-column: 1 / -1;
}
input,
select,
textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  font: inherit;
  background: #fff;
}
.file-input input {
  padding: 12px;
}
.file-input span {
  color: #6b7280;
  font-weight: 400;
}
.upload-card .actions {
  margin-top: 16px;
}
.error-text {
  margin-top: 12px;
  color: #dc2626;
  font-weight: 600;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-card span,
.summary-card small {
  color: #6b7280;
}
.summary-card strong {
  font-size: 28px;
}
.result-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  gap: 18px;
}
.markdown-card {
  grid-column: 1 / -1;
}
.section-head,
.suggestion-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.eyebrow {
  margin: 0;
  color: #2563eb;
  font-weight: 700;
}
.badge,
.tag {
  display: inline-flex;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  padding: 4px 10px;
  color: #374151;
  background: #f9fafb;
  margin: 6px 6px 0 0;
}
.warning-list {
  margin-top: 16px;
  padding: 14px;
  border-left: 4px solid #111827;
  background: #f9fafb;
}
.warning-list p {
  margin: 8px 0 0;
  color: #374151;
}
.source-note {
  margin: 8px 0 0;
  color: #6b7280;
  line-height: 1.6;
}
.suggestion-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  margin-top: 12px;
}
.suggestion-card p {
  color: #374151;
  line-height: 1.6;
}
.suggestion-card pre {
  white-space: pre-wrap;
  background: #f3f4f6;
  padding: 12px;
  border-radius: 8px;
  color: #111827;
}
.risk {
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 700;
}
.risk-high {
  color: #b91c1c;
  background: #fee2e2;
}
.risk-medium {
  color: #92400e;
  background: #fef3c7;
}
.risk-low {
  color: #166534;
  background: #dcfce7;
}
.risk-note {
  color: #b45309;
}
.markdown-card textarea {
  margin-top: 12px;
  min-height: 360px;
  font-family: Consolas, 'Courier New', monospace;
  line-height: 1.6;
}
.markdown-card .actions {
  margin-top: 14px;
}
@media (max-width: 860px) {
  .polish-hero,
  .result-grid,
  .summary-grid,
  .form-grid {
    grid-template-columns: 1fr;
    display: grid;
  }
  .polish-hero {
    display: block;
  }
}
</style>
