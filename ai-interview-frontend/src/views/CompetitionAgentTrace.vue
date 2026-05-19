<template>
  <div class="competition-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">证据附录 / Career-AgentOS Preview</p>
        <h1>三岗位 Agent 业务链路证据页</h1>
        <p class="lead">
          本页不作为普通用户功能入口。它用于答辩追问时证明：系统能把 demo 简历样本转成证据识别、岗位差距、简历润色、面试追问、报告任务和数据门禁。
          默认展示评委可读摘要，原始 JSON 只放在折叠区。
        </p>
      </div>
      <router-link class="primary-link" to="/competition/opc-ai-workflow">返回 OPC 评委页</router-link>
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

    <div v-if="loading" class="state">正在加载 Agent 证据链...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <template v-else>
      <section class="summary-grid">
        <article class="metric">
          <span>案例来源</span>
          <strong>{{ trace.sample_origin || '-' }}</strong>
          <p>仅用于 demo/preview</p>
        </article>
        <article class="metric">
          <span>训练用途</span>
          <strong>{{ trace.for_training ? '可训练' : '不可训练' }}</strong>
          <p>真实训练前必须换成授权样本</p>
        </article>
        <article class="metric">
          <span>业务链路</span>
          <strong>{{ stepCards.length }} 步</strong>
          <p>证据、润色、追问、报告、任务、门禁</p>
        </article>
        <article class="metric">
          <span>JSONL 结构预览</span>
          <strong>{{ sftSummary.counts?.train_preview_records || 0 }} 条</strong>
          <p>ready_for_real_training=false</p>
        </article>
      </section>

      <section class="business-loop">
        <div class="section-head">
          <div>
            <p class="eyebrow">Business Loop</p>
            <h2>评委默认看到的业务闭环</h2>
          </div>
        </div>
        <div class="loop-grid">
          <article v-for="item in loopItems" :key="item.title" class="loop-item">
            <span>{{ item.index }}</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.description }}</p>
          </article>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <div>
            <p class="eyebrow">Agent Evidence Cards</p>
            <h2>Agent 证据卡</h2>
          </div>
          <span>{{ stepCards.length }} 个步骤</span>
        </div>
        <div class="timeline">
          <article v-for="card in stepCards" :key="card.step" class="step-panel">
            <div class="step-top">
              <span class="step-index">{{ card.step }}</span>
              <div>
                <h3>{{ card.title }}</h3>
                <p>{{ card.agent }}</p>
              </div>
            </div>

            <div class="evidence-grid">
              <div>
                <strong>输入证据</strong>
                <ul>
                  <li v-for="item in card.inputs" :key="item">{{ item }}</li>
                </ul>
              </div>
              <div>
                <strong>Agent 判断</strong>
                <ul>
                  <li v-for="item in card.decisions" :key="item">{{ item }}</li>
                </ul>
              </div>
              <div>
                <strong>输出结果</strong>
                <ul>
                  <li v-for="item in card.outputs" :key="item">{{ item }}</li>
                </ul>
              </div>
              <div>
                <strong>风险边界</strong>
                <ul>
                  <li v-for="item in card.guardrails" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <p class="judge-note">{{ card.takeaway }}</p>

            <details class="raw-details">
              <summary>查看原始证据 JSON</summary>
              <pre>{{ formatOutput(card.rawOutput) }}</pre>
            </details>
          </article>
        </div>
      </section>

      <section class="two-column">
        <article class="panel">
          <h2>规则门禁 Preview</h2>
          <p class="muted">
            这里是沙盘规则评分示例，不是真实模型调用、真实 holdout eval 或 fine-tuned model 结果。
          </p>
          <div v-if="evalRows.length" class="eval-table">
            <div v-for="row in evalRows" :key="row.model_variant" class="eval-row">
              <div class="eval-row-main">
                <span>{{ evalVariantLabel(row.model_variant) }}</span>
                <strong>{{ evalGateLabel(row) }}</strong>
              </div>
              <details class="score-details">
                <summary>查看七维规则分</summary>
                <div class="eval-row-dims">
                  <span>总分 {{ row.total_score }}/35</span>
                  <span>聚焦 {{ row.focus_score }}</span>
                  <span>证据 {{ row.evidence_score }}</span>
                  <span>深度 {{ row.depth_score }}</span>
                  <span>润色 {{ row.polish_score }}</span>
                  <span>岗位 {{ row.role_fit_score }}</span>
                  <span>格式 {{ row.format_score }}</span>
                  <span>报告 {{ row.report_score }}</span>
                </div>
              </details>
            </div>
          </div>
          <p v-if="evalBoundary" class="eval-boundary">{{ evalBoundary }}</p>
        </article>
        <article class="panel">
          <h2>JSONL Schema Preview / 数据治理门禁</h2>
          <p class="muted">
            这里仅验证后训练数据结构和准入条件。当前真实授权样本不足，不能宣称已完成真实 OpenAI SFT。
          </p>
          <div class="gate-grid">
            <span>ready_for_real_training={{ String(sftSummary.ready_for_real_training || false) }}</span>
            <span>real_authorized={{ sftSummary.counts?.real_authorized || 0 }}</span>
            <span>demo_constructed={{ sftSummary.counts?.demo_constructed || 0 }}</span>
          </div>
          <div v-if="visibleSftRecords.length" class="sft-records">
            <article v-for="record in visibleSftRecords" :key="record.record_id" class="sft-record">
              <div class="sft-record-head">
                <strong>{{ taskLabel(record.task_type) }}</strong>
                <span>{{ record.sample_origin }} / for_training={{ String(record.for_training) }}</span>
              </div>
              <p class="record-id">{{ record.record_id }}</p>
              <p class="assistant-summary">{{ summarizeAssistantPreview(record) }}</p>
            </article>
          </div>
          <p v-else class="muted">当前案例暂无已校验的 JSONL Schema Preview 记录。</p>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  getCompetitionAgentTrace,
  getCompetitionCases,
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
const sftRecords = computed(() => sftPreview.value?.preview_records || [])
const visibleSftRecords = computed(() => {
  return sftRecords.value.filter(record => {
    const metadata = record.metadata || {}
    return (metadata.case_id || record.case_id) === selectedCaseId.value
  })
})
const evalRows = computed(() => evalPreview.value?.score_rows || [])
const evalBoundary = computed(() => {
  if (evalPreview.value?.claim_boundary) {
    return evalPreview.value.claim_boundary
  }
  const summary = evalPreview.value?.summary || ''
  const line = summary
    .split('\n')
    .find(item => item.includes('说明') || item.toLowerCase().includes('not a real'))
  return line ? line.replace(/^-\s*/, '') : ''
})
const stepCards = computed(() => (trace.value.steps || []).map(buildStepCard))
const loopItems = computed(() => [
  {
    index: '01',
    title: '输入简历',
    description: firstOutput('ResumeEvidenceAgent', 'evidence_items') || '读取 demo 简历证据，不使用真实用户数据。'
  },
  {
    index: '02',
    title: '证据识别',
    description: '区分直接证据、间接证据和缺失证据，避免把岗位知识库写成个人经历。'
  },
  {
    index: '03',
    title: '岗位差距',
    description: firstOutput('GapAnalysisAgent', 'gaps') || '把目标岗位能力要求映射为候选人的训练缺口。'
  },
  {
    index: '04',
    title: '润色与追问',
    description: firstPolishSuggestion() || '润色只能基于已有证据，追问围绕缺口能力。'
  },
  {
    index: '05',
    title: '报告与任务',
    description: firstTask() || '生成报告摘要和可执行学习任务。'
  },
  {
    index: '06',
    title: '门禁与预览',
    description: '规则门禁和 JSONL Schema Preview 只说明结构，不代表真实训练完成。'
  }
])

function sortCases(items) {
  const order = Object.fromEntries(CASE_ORDER.map((caseId, index) => [caseId, index]))
  return [...items].sort((a, b) => (order[a.case_id] ?? 99) - (order[b.case_id] ?? 99))
}

function formatOutput(value) {
  return JSON.stringify(value || {}, null, 2)
}

function asList(value, fallback = '暂无可展示摘要') {
  if (!value) return [fallback]
  if (Array.isArray(value)) {
    return value.slice(0, 3).map(item => {
      if (typeof item === 'string') return item
      return item.ability ||
        item.title ||
        item.question ||
        item.task ||
        item.section ||
        item.polish_suggestion ||
        item.practice ||
        item.acceptance ||
        item.diagnosis ||
        item.summary ||
        '结构化结果已生成，详见原始证据'
    })
  }
  if (typeof value === 'string') return [value]
  return [value.summary || value.claim || value.question || value.polish_suggestion || '结构化结果已生成，详见原始证据']
}

function findStep(agent) {
  return (trace.value.steps || []).find(step => step.agent === agent)
}

function firstOutput(agent, key) {
  const items = findStep(agent)?.output?.[key]
  const first = Array.isArray(items) ? items[0] : null
  if (!first) return ''
  if (first.ability && first.evidence_status) {
    return `${first.ability}：${first.evidence_status}，${first.risk || first.diagnosis || '需要继续验证'}`
  }
  if (first.ability && first.gap_level) {
    return `${first.ability}：差距 ${first.gap_level}，${first.diagnosis || '需要追问验证'}`
  }
  return first.title || first.task || first.question || ''
}

function firstPolishSuggestion() {
  const sections = findStep('ResumePolishAgent')?.output?.section_suggestions || []
  const first = sections[0]
  return first ? `${first.section || '简历段落'}：${first.polish_suggestion || first.suggestion || first.action || '基于证据调整表达'}` : ''
}

function firstTask() {
  const tasks = findStep('LearningTaskAgent')?.output?.tasks || []
  const first = tasks[0]
  return first ? `${first.title || first.task}：${first.acceptance || first.checkpoint || '需要可验收产出'}` : ''
}

function buildStepCard(step) {
  const output = step.output || {}
  const base = {
    step: step.step,
    agent: step.agent,
    title: step.title,
    rawOutput: output,
    inputs: ['demo_constructed 简历样本', '目标岗位画像', '前序 Agent 输出'],
    decisions: ['按证据和岗位要求生成结构化判断'],
    outputs: ['生成可追溯中间结果'],
    guardrails: step.warnings?.length ? step.warnings : ['仅用于 demo/preview，不进入真实训练'],
    takeaway: '评委可看到该步骤的输入、判断、输出和风险边界。'
  }

  switch (step.agent) {
    case 'ResumeEvidenceAgent':
      return {
        ...base,
        inputs: ['demo 简历文本', '目标岗位能力要求'],
        decisions: asList(output.evidence_items).map(item => `识别证据：${item}`),
        outputs: asList(output.evidence_items).map(item => `形成证据链：${item}`),
        guardrails: ['岗位知识库只能作为要求参考，不能写成候选人经历'],
        takeaway: '这是后续润色、追问和报告的事实基础。'
      }
    case 'RoleProfileAgent':
      return {
        ...base,
        inputs: ['目标岗位', '岗位知识库参考'],
        decisions: asList(output.core_abilities).map(item => `核心能力：${item}`),
        outputs: asList(output.role_requirements).map(item => `岗位要求：${item}`),
        guardrails: ['岗位画像是参考标准，不是候选人真实经历'],
        takeaway: '评委能看到系统不是随机问答，而是先建立岗位评价标准。'
      }
    case 'GapAnalysisAgent':
      return {
        ...base,
        inputs: ['简历证据链', '岗位画像'],
        decisions: asList(output.gaps).map(item => `能力缺口：${item}`),
        outputs: asList(output.gaps).map(item => `追问方向：${item}`),
        guardrails: ['缺口只说明需要验证，不直接判定候选人不具备能力'],
        takeaway: '能力差距把诊断、追问和学习任务连接起来。'
      }
    case 'ResumePolishAgent':
      return {
        ...base,
        inputs: ['简历证据链', '能力差距', '岗位画像'],
        decisions: asList(output.overall_strategy || output.section_suggestions).map(item => `润色策略：${item}`),
        outputs: asList(output.section_suggestions).map(item => `润色建议：${item}`),
        guardrails: step.warnings?.length ? step.warnings : ['不能新增公司、项目、时间、证书、指标或技术栈'],
        takeaway: '简历润色强调“可改但不造假”，这是区别普通生成式改写的关键。'
      }
    case 'InterviewFollowupAgent':
      return {
        ...base,
        inputs: ['能力缺口', '简历证据状态'],
        decisions: [`追问目标：${output.target_ability || '围绕缺口能力'}`, `追问依据：${output.evidence_focus || output.reason || '要求候选人补充具体证据'}`],
        outputs: [`问题：${output.question || '生成证据追问'}`],
        guardrails: ['追问只要求候选人说明经历，不替候选人编经历'],
        takeaway: '面试不再随机提问，而是围绕证据缺口验证能力。'
      }
    case 'ReportAgent':
      return {
        ...base,
        inputs: ['证据链', '能力差距', '追问结果'],
        decisions: asList(output.top_gaps).map(item => `报告重点：${item}`),
        outputs: asList(output.next_actions || output.summary).map(item => `行动建议：${item}`),
        guardrails: ['报告建议必须能回到证据和训练任务'],
        takeaway: '报告把一次面试转成可继续训练的结果。'
      }
    case 'LearningTaskAgent':
      return {
        ...base,
        inputs: ['能力差距', '报告建议'],
        decisions: asList(output.tasks).map(item => `任务设计：${item}`),
        outputs: asList(output.tasks).map(item => `可验收任务：${item}`),
        guardrails: ['任务必须有材料、练习、验收方式或预计耗时'],
        takeaway: '学习任务让诊断结果从“知道问题”变成“可执行训练”。'
      }
    case 'DataGovernanceAgent':
      return {
        ...base,
        inputs: ['样本来源', '授权状态', '训练用途'],
        decisions: [`样本来源：${output.sample_origin || 'demo_constructed'}`, `训练用途：for_training=${String(output.for_training)}`],
        outputs: [`展示用途：for_competition_demo=${String(output.for_competition_demo)}`],
        guardrails: ['demo 样本不得进入真实训练，也不能说成真实用户数据'],
        takeaway: '数据治理是后训练和答辩边界的硬门禁。'
      }
    case 'EvalAgent':
      return {
        ...base,
        inputs: ['Agent Trace', '规则评分维度'],
        decisions: ['执行七维规则门禁', output.judge_note || '仅用于 preview'],
        outputs: ['输出聚焦度、证据约束、深度、润色、岗位匹配、格式、报告七维检查'],
        guardrails: ['这不是真实模型实测，也不是 fine-tuned model 结果'],
        takeaway: '规则门禁用于解释质量控制方式，不用于夸大效果。'
      }
    case 'SFTPreviewAgent':
      return {
        ...base,
        inputs: ['Trace 输出', '样本准入规则', 'JSONL 结构'],
        decisions: [`ready_for_real_training=${String(output.ready_for_real_training || false)}`],
        outputs: asList(output.preview_tasks).map(item => `预览任务：${item}`),
        guardrails: ['真实训练前需要授权样本、人工复核、PII 扫描和 holdout eval'],
        takeaway: 'JSONL Schema Preview 只证明数据结构和门禁设计，不证明已经训练。'
      }
    default:
      return base
  }
}

function evalVariantLabel(value) {
  if (value === 'baseline_prompt_preview') return '规则基线 Preview'
  if (value === 'agent_optimized') return 'Agent 链路规则自检'
  return value || 'Preview'
}

function evalGateLabel(row) {
  if (row.model_variant === 'baseline_prompt_preview') return '需人工复核'
  if (row.model_variant === 'agent_optimized') return '规则自检示例'
  return '规则预览'
}

function taskLabel(value) {
  const labels = {
    interview_followup_generation: '追问生成样本结构',
    resume_polish_generation: '简历润色样本结构',
    report_feedback_generation: '报告反馈样本结构',
    interview_followup_preview: '追问生成结构预览',
    evidence_bound_resume_polish_preview: '证据约束润色结构预览'
  }
  return labels[value] || '未命名结构预览'
}

function summarizeAssistantPreview(record) {
  const assistant = (record.messages || []).find(message => message.role === 'assistant')
  const content = assistant?.content || ''
  if (!content) return '该记录暂无 assistant 输出预览。'
  try {
    const parsed = JSON.parse(content)
    const readable = parsed.question ||
      parsed.suggestion ||
      parsed.summary ||
      parsed.polish_suggestion ||
      parsed.overall_strategy
    if (readable) return String(readable)
    return '结构化输出已生成，具体字段见原始样本文件。'
  } catch {
    return content.slice(0, 160)
  }
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
    const caseResult = await getCompetitionCases()
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
  font-weight: 800;
}

h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.25;
}

h2 {
  margin: 0;
  color: #111827;
  font-size: 20px;
}

h3 {
  margin: 0;
  color: #111827;
  font-size: 16px;
}

.lead {
  max-width: 780px;
  color: #4b5563;
  line-height: 1.7;
}

.primary-link {
  flex-shrink: 0;
  padding: 10px 16px;
  border-radius: 8px;
  background: #0f766e;
  color: white;
  text-decoration: none;
  font-weight: 800;
}

.notice,
.metric,
.panel,
.step-panel,
.business-loop {
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
  line-height: 1.7;
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
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 800;
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
.two-column,
.loop-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 22px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.two-column {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric {
  padding: 16px;
}

.metric span,
.muted,
.metric p {
  color: #6b7280;
  font-size: 13px;
}

.metric strong {
  display: block;
  margin-top: 8px;
  color: #111827;
  font-size: 20px;
  overflow-wrap: anywhere;
}

.business-loop,
.section {
  margin-bottom: 22px;
}

.business-loop {
  padding: 16px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}

.section-head span {
  color: #6b7280;
  font-size: 13px;
}

.loop-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin-bottom: 0;
}

.loop-item {
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
}

.loop-item span {
  display: inline-flex;
  width: 32px;
  height: 24px;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
  border-radius: 999px;
  background: #ccfbf1;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.loop-item p {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
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
  margin-bottom: 14px;
}

.step-index {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 800;
}

.step-top p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.evidence-grid > div {
  padding: 12px;
  border-radius: 8px;
  background: #f8fafc;
}

.evidence-grid strong {
  color: #0f172a;
  font-size: 13px;
}

ul {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #374151;
  font-size: 13px;
  line-height: 1.65;
}

.judge-note {
  margin: 14px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #ecfeff;
  color: #155e75;
  font-size: 13px;
  line-height: 1.65;
}

.raw-details {
  margin-top: 12px;
}

.raw-details summary {
  cursor: pointer;
  color: #0f766e;
  font-size: 13px;
  font-weight: 800;
}

pre {
  overflow: auto;
  max-height: 280px;
  margin: 12px 0 0;
  padding: 12px;
  border-radius: 8px;
  background: #111827;
  color: #f9fafb;
  font-size: 12px;
  line-height: 1.55;
}

.eval-table,
.sft-records {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.eval-row,
.sft-record {
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
  color: #374151;
  font-size: 13px;
}

.eval-row-main,
.sft-record-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.eval-row strong,
.sft-record strong {
  color: #111827;
}

.score-details {
  margin-top: 8px;
}

.score-details summary {
  cursor: pointer;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.eval-row-dims {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.eval-row-dims span,
.gate-grid span {
  padding: 4px 7px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
}

.eval-boundary {
  margin: 12px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}

.gate-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.sft-record-head span,
.record-id,
.assistant-summary {
  color: #6b7280;
  font-size: 12px;
}

.record-id {
  margin: 6px 0 0;
  word-break: break-all;
}

.assistant-summary {
  margin: 8px 0 0;
  line-height: 1.65;
}

@media (max-width: 980px) {
  .summary-grid,
  .loop-grid,
  .evidence-grid,
  .two-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-head,
  .notice,
  .section-head {
    display: block;
  }

  .summary-grid,
  .loop-grid,
  .evidence-grid,
  .two-column {
    grid-template-columns: 1fr;
  }

  .primary-link {
    display: inline-block;
    margin-top: 12px;
  }
}
</style>
