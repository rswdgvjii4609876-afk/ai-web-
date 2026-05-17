<template>
  <div class="competition-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Career-AgentOS 技术展示</p>
        <h1>多 Agent 就业能力诊断演示闭环</h1>
        <p class="lead">
          展示三岗位沙盘样本、Agent Trace、证据约束简历润色、Eval Preview 和 SFT Preview。当前内容为比赛演示数据，不代表真实用户训练样本或真实 OpenAI 微调结果。
        </p>
      </div>
      <router-link class="primary-link" to="/resume/upload">进入真实流程</router-link>
    </header>

    <section class="notice">
      <strong>边界说明</strong>
      <span>{{ claimBoundary }}</span>
    </section>

    <section class="case-tabs" aria-label="演示案例">
      <button
        v-for="item in cases"
        :key="item.case_id"
        :class="{ active: item.case_id === selectedCaseId }"
        type="button"
        @click="selectCase(item.case_id)"
      >
        {{ item.target_role }}
      </button>
    </section>

    <div v-if="loading" class="state">正在加载 Agent Trace...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <template v-else>
      <section class="summary-grid">
        <article class="metric">
          <span>样本来源</span>
          <strong>{{ trace.sample_origin }}</strong>
        </article>
        <article class="metric">
          <span>训练用途</span>
          <strong>{{ trace.for_training ? '可训练' : '不可训练' }}</strong>
        </article>
        <article class="metric">
          <span>Eval 总分</span>
          <strong>{{ trace.eval_score?.total_score || '-' }}/35</strong>
        </article>
        <article class="metric">
          <span>SFT Preview</span>
          <strong>{{ sftSummary.counts?.train_preview_records || 0 }} 条</strong>
        </article>
      </section>

      <section class="section">
        <div class="section-head">
          <h2>Agent 时间线</h2>
          <span>{{ trace.steps?.length || 0 }} 个步骤</span>
        </div>
        <div class="timeline">
          <article v-for="step in trace.steps || []" :key="step.step" class="step-panel">
            <div class="step-top">
              <span class="step-index">{{ step.step }}</span>
              <div>
                <h3>{{ step.title }}</h3>
                <p>{{ step.agent }}</p>
              </div>
            </div>
            <ul v-if="step.warnings?.length" class="warning-list">
              <li v-for="warning in step.warnings" :key="warning">{{ warning }}</li>
            </ul>
            <pre>{{ formatOutput(step.output) }}</pre>
          </article>
        </div>
      </section>

      <section class="two-column">
        <article class="panel">
          <h2>Eval Preview</h2>
          <p class="muted">七维规则评分，仅用于沙盘展示；baseline_prompt_preview 不是实际模型调用。</p>
          <div v-if="evalRows.length" class="eval-table">
            <div v-for="row in evalRows" :key="row.model_variant" class="eval-row">
              <span>{{ row.model_variant }}</span>
              <strong>{{ row.total_score }}/35</strong>
            </div>
          </div>
          <div class="score-grid">
            <span>能力聚焦 {{ trace.eval_score?.focus_score || '-' }}</span>
            <span>证据约束 {{ trace.eval_score?.evidence_score || '-' }}</span>
            <span>追问深度 {{ trace.eval_score?.depth_score || '-' }}</span>
            <span>润色可执行 {{ trace.eval_score?.polish_score || '-' }}</span>
            <span>岗位贴合 {{ trace.eval_score?.role_fit_score || '-' }}</span>
            <span>格式稳定 {{ trace.eval_score?.format_score || '-' }}</span>
            <span>报告可用 {{ trace.eval_score?.report_score || '-' }}</span>
          </div>
          <p v-if="evalBoundary" class="eval-boundary">{{ evalBoundary }}</p>
        </article>
        <article class="panel">
          <h2>SFT Preview</h2>
          <p class="muted">仅验证数据结构，真实训练前必须替换为授权、人工复核样本。</p>
          <ul class="compact-list">
            <li v-for="task in sftSummary.tasks || []" :key="task">{{ task }}</li>
          </ul>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  getCompetitionAgentTrace,
  getCompetitionDemoCases,
  getCompetitionEvalPreview,
  getCompetitionSftPreview
} from '../api/competition'

const CASE_ORDER = ['python_backend', 'product_assistant', 'hr_specialist']

const cases = ref([])
const claimBoundary = ref('演示样本为 demo_constructed，for_training=false。')
const selectedCaseId = ref('')
const trace = ref({})
const evalPreview = ref({})
const sftPreview = ref({})
const loading = ref(false)
const error = ref('')

const sftSummary = computed(() => sftPreview.value?.summary || {})
const evalRows = computed(() => evalPreview.value?.score_rows || [])
const evalBoundary = computed(() => {
  const summary = evalPreview.value?.summary || ''
  const line = summary.split('\n').find(item => item.includes('说明'))
  return line ? line.replace(/^-\s*/, '') : ''
})

function sortCases(items) {
  const order = Object.fromEntries(CASE_ORDER.map((caseId, index) => [caseId, index]))
  return [...items].sort((a, b) => (order[a.case_id] ?? 99) - (order[b.case_id] ?? 99))
}

function formatOutput(value) {
  return JSON.stringify(value || {}, null, 2)
}

async function selectCase(caseId) {
  selectedCaseId.value = caseId
  loading.value = true
  error.value = ''
  try {
    trace.value = await getCompetitionAgentTrace(caseId)
    evalPreview.value = await getCompetitionEvalPreview(caseId)
  } catch (err) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const caseResult = await getCompetitionDemoCases()
    cases.value = sortCases(caseResult.items || [])
    claimBoundary.value = caseResult.claim_boundary || claimBoundary.value
    sftPreview.value = await getCompetitionSftPreview()
    if (cases.value.length) {
      await selectCase(cases.value[0].case_id)
    }
  } catch (err) {
    error.value = err.message || '加载失败'
  }
})
</script>

<style scoped>
.competition-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 24px 20px 48px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.eyebrow {
  margin: 0 0 6px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
}
h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
}
.lead {
  max-width: 760px;
  color: #4b5563;
  line-height: 1.7;
}
.primary-link {
  flex-shrink: 0;
  padding: 10px 16px;
  border-radius: 8px;
  background: #4f46e5;
  color: white;
  text-decoration: none;
  font-weight: 700;
}
.notice,
.metric,
.panel,
.step-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: white;
}
.notice {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  color: #374151;
  border-left: 4px solid #0f766e;
}
.case-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 18px 0;
}
.case-tabs button {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: white;
  color: #374151;
  padding: 9px 12px;
  cursor: pointer;
}
.case-tabs button.active {
  border-color: #4f46e5;
  background: #eef2ff;
  color: #3730a3;
  font-weight: 700;
}
.state {
  padding: 24px;
  text-align: center;
  color: #6b7280;
}
.state.error {
  color: #b91c1c;
}
.summary-grid,
.two-column {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}
.metric {
  padding: 16px;
}
.metric span,
.muted {
  color: #6b7280;
  font-size: 13px;
}
.metric strong {
  display: block;
  margin-top: 8px;
  color: #111827;
  font-size: 20px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.section-head h2,
.panel h2 {
  margin: 0;
  color: #111827;
  font-size: 20px;
}
.section-head span {
  color: #6b7280;
  font-size: 13px;
}
.timeline {
  display: grid;
  gap: 12px;
}
.step-panel,
.panel {
  padding: 16px;
}
.step-top {
  display: flex;
  gap: 12px;
  align-items: center;
}
.step-index {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #eef2ff;
  color: #3730a3;
  font-weight: 800;
}
.step-top h3 {
  margin: 0;
  font-size: 16px;
}
.step-top p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}
.warning-list {
  margin: 12px 0;
  color: #92400e;
}
pre {
  overflow: auto;
  max-height: 280px;
  margin: 14px 0 0;
  padding: 12px;
  border-radius: 8px;
  background: #111827;
  color: #f9fafb;
  font-size: 12px;
  line-height: 1.55;
}
.score-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.eval-table {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.eval-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  color: #374151;
  font-size: 13px;
}
.eval-row strong {
  color: #111827;
}
.eval-boundary {
  margin: 12px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}
.score-grid span,
.compact-list li {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 13px;
}
.compact-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0;
  margin: 12px 0 0;
  list-style: none;
}
@media (max-width: 760px) {
  .page-head {
    display: block;
  }
  .primary-link {
    display: inline-block;
    margin-top: 12px;
  }
}
</style>
