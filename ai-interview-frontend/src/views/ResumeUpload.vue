<template>
  <div class="container">
    <div class="card" style="max-width:600px;margin:40px auto">
      <h2 style="margin-bottom:20px">新建面试</h2>

      <!-- Step 1: 上传简历 -->
      <div v-if="step === 1">
        <div class="form-group">
          <label>上传简历 (PDF)</label>
          <div class="upload-area" @click="$refs.fileInput.click()" @dragover.prevent @drop.prevent="onDrop">
            <input ref="fileInput" type="file" accept=".pdf" @change="onFileChange" hidden />
            <p v-if="!file" style="color:#6b7280">点击或拖拽上传 PDF 简历</p>
            <p v-else>📎 {{ file.name }}</p>
          </div>
        </div>
        <div class="form-group">
          <label>目标岗位</label>
          <input v-model="targetPosition" placeholder="例如：Python后端开发工程师 / 前端开发工程师 / 产品助理 / 人力资源专员" />
        </div>
        <div class="card api-test-card" style="margin-bottom:16px">
          <div class="api-test-head">
            <div>
              <h3 style="margin-bottom:8px">选择本次测评 AI</h3>
              <p class="api-test-desc">
                开始解析简历前，先选择这一次要使用的 AI 服务商和模型。你可以先检测连接是否成功，确认无误后再开始解析。
              </p>
            </div>
          </div>
          <div class="form-row compact-form-row">
            <div class="form-group">
              <label>AI 服务商</label>
              <select v-model="aiTestProvider" @change="handleAiProviderChange">
                <option v-for="option in aiProviderOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label>使用模型</label>
              <input
                v-model="aiTestModel"
                :placeholder="aiTestModelPlaceholder"
                :list="aiModelDatalistId"
              />
              <datalist :id="aiModelDatalistId">
                <option
                  v-for="option in activeAiModelOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </datalist>
            </div>
          </div>
          <div class="api-test-actions">
            <button
              class="btn-secondary"
              @click="handleTestAiConnection"
              :disabled="testingAiConnection || uploading || starting"
            >
              {{ testingAiConnection ? '检测中...' : `检测 ${activeAiProviderLabel} 连接` }}
            </button>
            <p v-if="aiTestMessage" :class="aiTestSuccess ? 'success-msg inline-msg' : 'error inline-msg'">
              {{ aiTestMessage }}
            </p>
          </div>
          <p class="api-test-current-selection">
            本次解析将使用：{{ activeAiProviderLabel }} / {{ currentAiModelDisplay }}
          </p>
          <p class="api-test-usage-note">
            当前这里选中的服务商和模型，会用于这一次简历解析；但不会修改你个人设置里保存的默认配置。
          </p>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary" style="width:100%" @click="handleUpload" :disabled="!file || uploading">
          {{ uploading ? '上传中...' : '上传并解析简历' }}
        </button>
      </div>

      <!-- Step 1.5: 解析动画 -->
      <div v-if="step === 'parsing'" class="parsing-stage">
        <div class="parsing-icon">🔍</div>
        <h3>{{ parsingTitle }}</h3>
        <div class="progress-bar-wrapper">
          <div class="progress-bar" :style="{ width: progress + '%' }"></div>
        </div>
        <p class="progress-text">{{ progress }}%</p>
        <div class="tips-area">
          <transition name="tip-fade" mode="out-in">
            <p class="tip-text" :key="currentTip">💡 {{ currentTip }}</p>
          </transition>
        </div>
      </div>

      <!-- Step 2: 解析结果 + 简历分析 + 面试配置 -->
      <div v-if="step === 2">
        <div class="parsed-info card" style="background:#f9fafb;margin-bottom:20px">
          <h3 style="margin-bottom:12px">✅ 简历解析完成</h3>
          <div v-if="parsedContent">
            <p v-if="parsedContent.name"><strong>姓名：</strong>{{ parsedContent.name }}</p>
            <p v-if="parsedContent.education"><strong>学历：</strong>{{ parsedContent.education }}</p>
            <p v-if="parsedContent.skills?.length"><strong>技能：</strong>{{ parsedContent.skills.join('、') }}</p>
            <p v-if="parsedContent.summary"><strong>概述：</strong>{{ parsedContent.summary }}</p>
          </div>
        </div>

        <div v-if="parseQualityVisible" class="card parse-quality-card">
          <div class="parse-quality-head">
            <h3>解析质量诊断</h3>
            <span :class="['parse-quality-status', parseQualityStatusClass(parseQuality.status)]">
              {{ parseQualityStatusLabel(parseQuality.status) }}
            </span>
          </div>
          <div class="parse-quality-grid">
            <div>
              <strong>{{ parseQuality.char_count || extractionDiagnostics.char_count || 0 }}</strong>
              <span>提取字符</span>
            </div>
            <div>
              <strong>{{ parseMethodLabel(parseQuality.best_method || extractionDiagnostics.best_method) }}</strong>
              <span>抽取方式</span>
            </div>
            <div>
              <strong>{{ extractionDiagnostics.ocr_used ? '已使用' : '未使用' }}</strong>
              <span>OCR fallback</span>
            </div>
          </div>
          <div v-if="parseMissingFieldLabels.length" class="parse-quality-section">
            <p class="parse-quality-label">待补字段</p>
            <div class="tag-list">
              <span v-for="item in parseMissingFieldLabels" :key="item" class="tag tag-red">{{ item }}</span>
            </div>
          </div>
          <ul v-if="parseQualityWarnings.length" class="parse-quality-warnings">
            <li v-for="item in parseQualityWarnings" :key="item">{{ item }}</li>
          </ul>
        </div>

        <!-- 简历分析报告 -->
        <div v-if="analysis" class="card analysis-card" style="margin-bottom:20px">
          <h3 style="margin-bottom:14px">简历与岗位匹配报告</h3>
          <div class="analysis-score" v-if="analysis.overall_score">
            <div class="score-badge" :style="{ background: scoreColor(analysis.overall_score) }">
              {{ analysis.overall_score }}
            </div>
            <span class="score-text">简历综合评分</span>
          </div>
          <div v-if="matchingMetrics" class="matching-metrics">
            <div class="metric-item">
              <strong>{{ percentText(matchingMetrics.keyword_coverage?.score) }}</strong>
              <span>关键词覆盖率</span>
            </div>
            <div class="metric-item">
              <strong>{{ matchingMetrics.semantic_score ?? '-' }}</strong>
              <span>语义分</span>
              <em class="semantic-source">{{ semanticSourceLabel(matchingMetrics) }}</em>
            </div>
            <div class="metric-item">
              <strong>{{ matchingMetrics.rule_score ?? '-' }}</strong>
              <span>规则评分</span>
            </div>
            <div class="metric-item final">
              <strong>{{ matchingMetrics.final_score ?? '-' }}</strong>
              <span>最终匹配分</span>
            </div>
          </div>
          <div v-if="matchingMetrics?.evidence_basis?.length" class="analysis-section">
            <h4>可解释匹配依据</h4>
            <ul><li v-for="(item, i) in matchingMetrics.evidence_basis" :key="i">{{ item }}</li></ul>
          </div>
          <div v-if="abilityGapItems.length" class="analysis-section ability-gap-section">
            <h4>能力差距优先级</h4>
            <div class="ability-gap-list">
              <div v-for="item in abilityGapItems" :key="item.ability_id" class="ability-gap-item">
                <div class="ability-gap-head">
                  <strong>{{ item.name }}</strong>
                  <span>优先级 {{ item.priority_score }}</span>
                  <span class="evidence-status" :class="evidenceStatusClass(item.evidence_status)">
                    {{ evidenceStatusLabel(item.evidence_status) }}
                  </span>
                </div>
                <div class="ability-gap-meta">
                  当前 {{ item.current_level }} / 要求 {{ item.required_level }} · 差距 {{ item.gap }} · 匹配 {{ item.match_score }}%
                </div>
                <p>{{ item.evidence_basis }}</p>
                <p v-if="item.evidence_status === 'claimed_only' || item.evidence_status === 'indirect'" class="evidence-status-hint">
                  {{ evidenceStatusHint(item.evidence_status) }}
                </p>
              </div>
            </div>
          </div>
          <div v-if="learningPrioritySummary.length" class="analysis-section">
            <h4>下一步学习优先事项</h4>
            <ul><li v-for="(item, i) in learningPrioritySummary" :key="i">{{ item }}</li></ul>
          </div>
          <div v-if="learningPlanTasks.length" class="analysis-section learning-task-bridge">
            <h4>能力提升计划</h4>
            <p>系统已生成 {{ learningPlanTasks.length }} 项学习任务。加入学习任务页后，可统一记录完成状态、学习笔记和导入导出进度。</p>
            <div class="analysis-actions">
              <button class="btn-secondary analysis-action-link" type="button" @click="addCurrentLearningPlanTasks">
                加入学习任务页
              </button>
              <router-link to="/learning-tasks" class="btn-secondary analysis-action-link">
                查看学习任务
              </router-link>
            </div>
            <p v-if="learningTaskMessage" class="learning-task-message">{{ learningTaskMessage }}</p>
          </div>
          <div v-if="resumeId" class="analysis-actions">
            <router-link :to="abilityDiagnosisLink" class="btn-secondary analysis-action-link">
              查看能力诊断
            </router-link>
            <router-link to="/learning-tasks" class="btn-secondary analysis-action-link">
              学习任务
            </router-link>
          </div>
          <p v-if="analysis.summary" class="analysis-summary">{{ analysis.summary }}</p>
          <div class="analysis-section" v-if="analysis.keyword_match?.length">
            <h4>🎯 匹配技能</h4>
            <div class="tag-list">
              <span v-for="k in analysis.keyword_match" :key="k" class="tag tag-green">{{ k }}</span>
            </div>
          </div>
          <div class="analysis-section" v-if="analysis.missing_keywords?.length">
            <h4>⚠️ 缺少技能</h4>
            <div class="tag-list">
              <span v-for="k in analysis.missing_keywords" :key="k" class="tag tag-red">{{ k }}</span>
            </div>
          </div>
          <div class="analysis-two-col">
            <div v-if="analysis.strengths?.length">
              <h4 style="color:#059669;margin-bottom:8px">✅ 优势</h4>
              <ul><li v-for="(s, i) in analysis.strengths" :key="i">{{ s }}</li></ul>
            </div>
            <div v-if="analysis.weaknesses?.length">
              <h4 style="color:#dc2626;margin-bottom:8px">❌ 不足</h4>
              <ul><li v-for="(w, i) in analysis.weaknesses" :key="i">{{ w }}</li></ul>
            </div>
          </div>
          <div class="analysis-section" v-if="analysis.suggestions?.length">
            <h4>💡 改进建议</h4>
            <ul><li v-for="(s, i) in analysis.suggestions" :key="i">{{ s }}</li></ul>
          </div>
        </div>

        <div v-if="hasEvidenceCard" class="card evidence-card" style="margin-bottom:20px">
          <h3 style="margin-bottom:12px">🧩 简历证据摘要</h3>
          <p class="evidence-desc">
            这部分会作为后续出题、追问和判断“证据是否充分”的参考依据。若证据不足，系统会优先提示追问而不是强行下结论。
          </p>
          <div class="tag-list evidence-stat-tags">
            <span v-if="resumeEvidence?.projects?.length" class="tag evidence-stat-tag">项目证据 {{ resumeEvidence.projects.length }}</span>
            <span v-if="resumeEvidence?.skills?.length" class="tag evidence-stat-tag">技能证据 {{ resumeEvidence.skills.length }}</span>
            <span v-if="resumeEvidence?.metrics?.length" class="tag evidence-stat-tag">指标证据 {{ resumeEvidence.metrics.length }}</span>
          </div>
          <div class="analysis-section" v-if="evidenceSummary.length">
            <h4>证据摘要</h4>
            <ul><li v-for="(item, index) in evidenceSummary" :key="index">{{ item }}</li></ul>
          </div>
          <div class="analysis-two-col">
            <div v-if="resumeEvidence?.ambiguity_flags?.length">
              <h4 style="color:#b45309;margin-bottom:8px">⚠️ 模糊表述风险</h4>
              <ul><li v-for="(item, index) in resumeEvidence.ambiguity_flags.slice(0, 4)" :key="index">{{ item }}</li></ul>
            </div>
            <div v-if="resumeEvidence?.missing_evidence_flags?.length">
              <h4 style="color:#dc2626;margin-bottom:8px">🕳️ 缺证据点</h4>
              <ul><li v-for="(item, index) in resumeEvidence.missing_evidence_flags.slice(0, 4)" :key="index">{{ item }}</li></ul>
            </div>
          </div>
          <div class="analysis-section" v-if="resumeEvidence?.followup_candidates?.length">
            <h4>建议追问点</h4>
            <ul><li v-for="(item, index) in resumeEvidence.followup_candidates.slice(0, 4)" :key="index">{{ item }}</li></ul>
          </div>
        </div>

        <div class="card knowledge-card" style="margin-bottom:20px">
          <div class="knowledge-header">
            <div>
              <h3 style="margin-bottom:8px">岗位画像库增强</h3>
              <p class="knowledge-desc">
                可选：选择目标岗位画像，让系统按岗位能力要求、评分规则和证据线索生成更贴近求职场景的问题。
              </p>
            </div>
            <router-link to="/knowledge-base" class="btn-secondary" style="display:inline-block;padding:8px 14px;border-radius:8px">
              管理岗位画像
            </router-link>
          </div>

          <div v-if="knowledgeLoading" class="knowledge-loading">正在加载岗位画像...</div>

          <template v-else>
            <div class="form-group">
              <label>选择要注入的岗位画像</label>
              <select v-model="selectedKnowledgeBaseId">
                <option value="">不使用岗位画像（默认按简历与岗位出题）</option>
                <option
                  v-for="item in knowledgeBaseOptions"
                  :key="item.knowledge_base_id"
                  :value="String(item.knowledge_base_id)"
                >
                  {{ item.title }} ｜ {{ item.target_position }} ｜ {{ item.source_label }}{{ matchScore(item) > 0 ? ' · 推荐' : '' }}
                </option>
              </select>
            </div>

            <p v-if="knowledgeBaseOptions.length === 0" class="knowledge-empty">
              你还没有创建岗位画像。建议先整理一份目标岗位的核心能力、任务和评分重点，测评效果会更稳定。
            </p>

            <div v-else-if="selectedKnowledgeBase" class="knowledge-preview">
              <div class="knowledge-tags">
                <span class="knowledge-tag">{{ selectedKnowledgeBase.title }}</span>
                <span class="knowledge-tag subtle">{{ selectedKnowledgeBase.target_position }}</span>
                <span :class="['knowledge-tag', selectedKnowledgeBase.scope === 'public' ? 'public-tag' : 'private-tag']">
                  {{ selectedKnowledgeBase.source_label }}
                </span>
              </div>
              <p class="knowledge-preview-text">{{ selectedKnowledgeBase.preview }}</p>
              <p v-if="selectedKnowledgeBase.focus_points" class="knowledge-detail">
                <strong>训练重点：</strong>{{ selectedKnowledgeBase.focus_points }}
              </p>
              <p v-if="selectedKnowledgeBase.interviewer_prompt" class="knowledge-detail">
                <strong>面试官要求：</strong>{{ selectedKnowledgeBase.interviewer_prompt }}
              </p>
            </div>
          </template>
        </div>

        <div class="form-group">
          <label>测评难度</label>
          <select v-model="difficulty">
            <option value="easy">简单 - 基础求职准备</option>
            <option value="medium">中等 - 岗位能力追问</option>
            <option value="hard">困难 - 压力场景与综合判断</option>
          </select>
        </div>
        <div class="form-group">
          <label>题目数量</label>
          <select v-model.number="totalQuestions">
            <option :value="3">3 题（快速模式）</option>
            <option :value="5">5 题（标准模式）</option>
            <option :value="8">8 题（深度模式）</option>
          </select>
        </div>
        <div class="card panel-mode-card" style="margin-bottom:16px">
          <label class="panel-mode-toggle">
            <input v-model="multiInterviewerEnabled" type="checkbox" />
            <span>
              <strong>多角色协同评估模式</strong>
              <small>内部由岗位面试官、就业指导老师和证据核查视角协同出题和评估，对外仍显示一个主持人。</small>
            </span>
          </label>
          <div v-if="multiInterviewerEnabled" class="panel-mode-preview">
            <div class="panel-preview-row">
              <span class="panel-preview-label">协同视角</span>
              <div class="panel-preview-tags">
                <span v-for="item in panelRoleHints" :key="item" class="panel-preview-tag">{{ item }}</span>
              </div>
            </div>
            <p class="panel-preview-note">
              外部仍然是单主持人流程；内部会综合岗位画像、岗位知识点、简历证据、表达逻辑和改进潜力做选题与追问。
            </p>
          </div>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <ul v-if="startErrorTips.length" class="error-tip-list">
          <li v-for="tip in startErrorTips" :key="tip">{{ tip }}</li>
        </ul>
        <button class="btn-primary" style="width:100%" @click="handleStart" :disabled="starting">
          {{ starting ? '生成测评题中...' : '开始模拟面试' }}
        </button>
      </div>

      <!-- Step 3: 面试准备动画 -->
      <div v-if="step === 'starting'" class="parsing-stage">
        <div class="ai-face-anim">
          <svg viewBox="0 0 80 80" width="80" height="80">
            <circle cx="40" cy="40" r="38" fill="white" stroke="#4f46e5" stroke-width="2"/>
            <ellipse cx="28" cy="36" rx="5" ry="6" fill="#1e1e1e">
              <animate attributeName="ry" values="6;1;6" dur="2s" repeatCount="indefinite"/>
            </ellipse>
            <ellipse cx="52" cy="36" rx="5" ry="6" fill="#1e1e1e">
              <animate attributeName="ry" values="6;1;6" dur="2s" repeatCount="indefinite"/>
            </ellipse>
            <path d="M30 52 Q40 60 50 52" stroke="#1e1e1e" stroke-width="2" fill="none" stroke-linecap="round"/>
          </svg>
        </div>
        <h3>{{ startingTitle }}</h3>
        <div class="progress-bar-wrapper">
          <div class="progress-bar" :style="{ width: startProgress + '%' }"></div>
        </div>
        <p class="progress-text">{{ startProgress }}%</p>
        <div class="tips-area">
          <transition name="tip-fade" mode="out-in">
            <p class="tip-text" :key="startTip">💡 {{ startTip }}</p>
          </transition>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { uploadResume, getResume } from '../api/resume'
import { startInterview } from '../api/interview'
import { getKnowledgeBases } from '../api/knowledgeBase'
import { getProfile, testAiConnection } from '../api/user'
import { evidenceStatusClass, evidenceStatusHint, evidenceStatusLabel } from '../utils/evidenceStatus'
import { normalizeResumeEvaluation } from '../utils/resumeEvaluation'
import { taskFromLearningPlan, upsertLearningTasksToServer } from '../utils/learningTasks'

const router = useRouter()
const route = useRoute()
const initialTargetPosition = Array.isArray(route.query.target_position)
  ? route.query.target_position[0]
  : route.query.target_position
const step = ref(1)
const file = ref(null)
const targetPosition = ref(initialTargetPosition || 'Python后端开发工程师')
const difficulty = ref('medium')
const totalQuestions = ref(5)
const multiInterviewerEnabled = ref(false)
const uploading = ref(false)
const starting = ref(false)
const error = ref('')
const resumeId = ref(null)
const parsedContent = ref(null)
const analysis = ref(null)
const resumeEvidence = ref(null)
const learningTaskMessage = ref('')
const evidenceSummary = ref([])
const knowledgeLoading = ref(false)
const knowledgeBases = ref([])
const selectedKnowledgeBaseId = ref('')
const panelRoleHints = ['岗位知识点', '项目追问', '沟通表达', '证据核查', '改进建议']

const aiProviderOptions = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'ChatGPT / OpenAI' }
]
const aiProviderLabels = {
  deepseek: 'DeepSeek',
  openai: 'ChatGPT / OpenAI'
}
const aiProviderDefaults = {
  deepseek: { model: 'deepseek-v4-flash' },
  openai: { model: 'gpt-5.2-chat-latest' }
}
const aiProviderModelOptions = {
  deepseek: [
    { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash（推荐）' },
    { value: 'deepseek-v4-pro', label: 'deepseek-v4-pro' },
    { value: 'deepseek-chat', label: 'deepseek-chat（旧版兼容，2026-07-24 停用）' },
    { value: 'deepseek-reasoner', label: 'deepseek-reasoner（旧版兼容，2026-07-24 停用）' }
  ],
  openai: [
    { value: 'gpt-5.2-chat-latest', label: 'gpt-5.2-chat-latest' },
    { value: 'gpt-5.2', label: 'gpt-5.2' },
    { value: 'gpt-5-mini', label: 'gpt-5-mini' }
  ]
}
const aiModelDatalistId = 'resume-upload-ai-model-options'
const aiTestProvider = ref('deepseek')
const aiTestModel = ref('')
const aiSavedModels = ref({
  deepseek: '',
  openai: ''
})
const testingAiConnection = ref(false)
const aiTestMessage = ref('')
const aiTestSuccess = ref(false)

const activeAiProviderLabel = computed(() => aiProviderLabels[aiTestProvider.value] || 'AI')
const activeAiModelOptions = computed(() => aiProviderModelOptions[aiTestProvider.value] || [])
const aiTestModelPlaceholder = computed(() => aiProviderDefaults[aiTestProvider.value]?.model || '')
const currentAiModelDisplay = computed(() => aiTestModel.value?.trim() || aiTestModelPlaceholder.value || '未选择模型')
const startErrorTips = computed(() => buildStartErrorTips(error.value))
const hasEvidenceCard = computed(() => {
  if (evidenceSummary.value.length) return true
  const payload = resumeEvidence.value || {}
  return [
    payload.projects,
    payload.skills,
    payload.metrics,
    payload.ambiguity_flags,
    payload.missing_evidence_flags,
    payload.followup_candidates
  ].some(item => Array.isArray(item) && item.length > 0)
})

const resumeEvaluation = computed(() => normalizeResumeEvaluation(analysis.value || {}))
const extractionDiagnostics = computed(() => analysis.value?.extraction_diagnostics || {})
const parseQuality = computed(() => analysis.value?.parse_quality || {})
const parseQualityVisible = computed(() => {
  return Boolean(parseQuality.value?.status || extractionDiagnostics.value?.best_method)
})
const parseMissingFieldLabels = computed(() => {
  const items = parseQuality.value?.missing_fields
  return Array.isArray(items) ? items.map(parseMissingFieldLabel) : []
})
const parseQualityWarnings = computed(() => {
  const warnings = parseQuality.value?.warnings || extractionDiagnostics.value?.warnings
  if (!Array.isArray(warnings)) return []
  return warnings.map(parseQualityWarningLabel).filter(Boolean).slice(0, 4)
})
const matchingMetrics = computed(() => resumeEvaluation.value.matchingMetrics || null)
const abilityGapProfile = computed(() => resumeEvaluation.value.abilityProfile || null)
const abilityGapItems = computed(() => {
  const topGaps = abilityGapProfile.value?.top_gaps
  const items = Array.isArray(topGaps) && topGaps.length ? topGaps : abilityGapProfile.value?.items
  return Array.isArray(items) ? items.slice(0, 5) : []
})
const learningPrioritySummary = computed(() => {
  const direct = resumeEvaluation.value.learningPrioritySummary
  return Array.isArray(direct) ? direct.slice(0, 5) : []
})
const learningPlan = computed(() => resumeEvaluation.value.learningPlan || null)
const learningPlanTasks = computed(() => {
  const tasks = learningPlan.value?.tasks
  return Array.isArray(tasks) ? tasks : []
})
const abilityDiagnosisLink = computed(() => ({
  path: '/ability-diagnosis',
  query: resumeId.value ? { resume_id: resumeId.value } : {}
}))

async function addCurrentLearningPlanTasks() {
  const tasks = learningPlanTasks.value.map((task, index) => taskFromLearningPlan(task, {
    target_position: targetPosition.value,
    resume_id: resumeId.value,
    source_type: 'learning_plan',
    source_id: `${resumeId.value || 'resume'}_plan_${task.task_id || task.ability_id || index}`
  }))
  try {
    await upsertLearningTasksToServer(tasks)
    learningTaskMessage.value = `已加入 ${tasks.length} 项账号学习任务。`
  } catch (e) {
    learningTaskMessage.value = e.message || '加入学习任务失败，请确认登录状态和服务器连接。'
  }
}

const selectedKnowledgeBase = computed(() => {
  const id = Number(selectedKnowledgeBaseId.value)
  if (!id) return null
  return knowledgeBases.value.find(item => item.knowledge_base_id === id) || null
})

const knowledgeBaseOptions = computed(() => {
  return [...knowledgeBases.value].sort((a, b) => {
    const scoreDiff = matchScore(b) - matchScore(a)
    if (scoreDiff !== 0) return scoreDiff
    const scopeDiff = ownershipScore(b) - ownershipScore(a)
    if (scopeDiff !== 0) return scopeDiff
    return new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime()
  })
})

// 解析动画相关
const progress = ref(0)
const parsingTitle = ref('正在上传简历...')
const currentTip = ref('')
let tipTimer = null
let progressTimer = null

const tips = [
  '面试前深呼吸，保持自信和冷静',
  '回答问题时用 STAR 法则：情境、任务、行动、结果',
  '不会的问题坦诚说不会，展示学习意愿比硬编更好',
  '准备好自我介绍，控制在1-2分钟',
  '面试回答中，思路和证据比空泛结论更重要',
  '实践经历要突出你的真实职责、行动和结果',
  '遇到不会的问题先说明理解，再表达学习计划',
  '面试官问"还有什么问题"时，准备2-3个有深度的问题',
  '简历上写的每段经历都要能展开讲清楚',
  '注意沟通表达，逻辑清晰比语速快更重要',
  '了解目标岗位的日常任务和能力要求，展示你的准备度',
  '回答时优先讲清场景、任务、行动和结果',
  '压力题先稳定情绪，再分步骤说明判断依据',
  '准备几个你在项目中解决的难题案例',
  '面试结束后及时复盘，记录不足之处'
]

const resumeStatusMeta = {
  queued: { progress: 12, title: '简历已上传，正在进入解析队列...' },
  extracting: { progress: 32, title: '正在提取 PDF 文本内容...' },
  parsing: { progress: 58, title: 'AI 正在结构化解析简历...' },
  evidencing: { progress: 72, title: '正在整理简历证据层...' },
  analyzing: { progress: 82, title: 'AI 正在生成简历分析报告...' },
  completed: { progress: 100, title: '解析完成，正在准备结果...' },
  failed: { progress: 100, title: '解析失败，正在返回结果...' }
}

function syncParsingStage(status) {
  const meta = resumeStatusMeta[status]
  if (!meta) return
  if (progress.value < meta.progress) {
    progress.value = meta.progress
  }
  parsingTitle.value = meta.title
}

function startTipRotation() {
  currentTip.value = tips[Math.floor(Math.random() * tips.length)]
  tipTimer = setInterval(() => {
    let next
    do { next = tips[Math.floor(Math.random() * tips.length)] } while (next === currentTip.value)
    currentTip.value = next
  }, 3000)
}

function startProgressAnimation() {
  progress.value = 0
  const stages = [
    { target: 15, speed: 200, title: '正在上传简历...' },
    { target: 35, speed: 300, title: '正在提取文本内容...' },
    { target: 60, speed: 400, title: 'AI 正在解析简历...' },
    { target: 80, speed: 500, title: 'AI 正在分析简历质量...' },
    { target: 92, speed: 800, title: '即将完成...' }
  ]
  let stageIdx = 0

  function tick() {
    if (stageIdx >= stages.length) return
    const stage = stages[stageIdx]
    if (progress.value < stage.target) {
      progress.value++
      parsingTitle.value = stage.title
      progressTimer = setTimeout(tick, stage.speed)
    } else {
      stageIdx++
      tick()
    }
  }
  tick()
}

function stopAnimations() {
  if (tipTimer) { clearInterval(tipTimer); tipTimer = null }
  if (progressTimer) { clearTimeout(progressTimer); progressTimer = null }
}

function applyAiProfile(data) {
  aiSavedModels.value = {
    deepseek: data?.deepseek_model || '',
    openai: data?.openai_model || ''
  }
  aiTestProvider.value = data?.ai_provider || 'deepseek'
  aiTestModel.value = aiSavedModels.value[aiTestProvider.value] || aiProviderDefaults[aiTestProvider.value]?.model || ''
}

function handleAiProviderChange() {
  aiTestMessage.value = ''
  aiTestSuccess.value = false
  aiTestModel.value = aiSavedModels.value[aiTestProvider.value] || aiProviderDefaults[aiTestProvider.value]?.model || ''
}

onMounted(async () => {
  try {
    const data = await getProfile()
    applyAiProfile(data)
  } catch (e) {
    console.error('鍔犺浇 AI 閰嶇疆澶辫触', e)
  }
})

onUnmounted(() => {
  stopAnimations()
  stopStartingAnimation()
})

function selectPdfFile(candidate) {
  if (!candidate) return
  if (!candidate.name?.toLowerCase().endsWith('.pdf')) {
    error.value = '仅支持上传 PDF 简历'
    file.value = null
    return
  }
  if (candidate.size > 10 * 1024 * 1024) {
    error.value = '文件大小不能超过 10MB'
    file.value = null
    return
  }
  error.value = ''
  file.value = candidate
}

function onFileChange(e) {
  selectPdfFile(e.target.files[0])
}
function onDrop(e) {
  selectPdfFile(e.dataTransfer.files[0])
}

function normalizePosition(value) {
  return (value || '').trim().toLowerCase()
}

function matchScore(item) {
  const target = normalizePosition(targetPosition.value)
  const current = normalizePosition(item?.target_position)
  if (!target || !current) return 0
  if (current === target) return 2
  if (current.includes(target) || target.includes(current)) return 1
  return 0
}

function ownershipScore(item) {
  return item?.scope === 'private' ? 1 : 0
}

async function loadKnowledgeBases() {
  knowledgeLoading.value = true
  try {
    const data = await getKnowledgeBases()
    knowledgeBases.value = data.items || []

    if (!selectedKnowledgeBaseId.value) {
      const bestMatch = [...knowledgeBases.value]
        .sort((a, b) => {
          const scoreDiff = matchScore(b) - matchScore(a)
          if (scoreDiff !== 0) return scoreDiff
          return ownershipScore(b) - ownershipScore(a)
        })[0]
      if (bestMatch && matchScore(bestMatch) > 0) {
        selectedKnowledgeBaseId.value = String(bestMatch.knowledge_base_id)
      }
    }
  } catch (e) {
    console.error('加载岗位画像失败:', e)
    knowledgeBases.value = []
  } finally {
    knowledgeLoading.value = false
  }
}

async function handleTestAiConnection() {
  aiTestMessage.value = ''
  aiTestSuccess.value = false
  testingAiConnection.value = true
  try {
    const result = await testAiConnection({
      provider: aiTestProvider.value,
      model: aiTestModel.value?.trim() || undefined
    })
    aiTestSuccess.value = true
    aiTestMessage.value = result?.message || `${activeAiProviderLabel.value} API 连接测试成功`
  } catch (e) {
    aiTestMessage.value = e.message
  } finally {
    testingAiConnection.value = false
  }
}

async function handleUpload() {
  error.value = ''
  uploading.value = true
  resumeEvidence.value = null
  evidenceSummary.value = []
  try {
    await getProfile()

    // 切换到解析动画
    step.value = 'parsing'
    startTipRotation()
    startProgressAnimation()

    const data = await uploadResume(file.value, targetPosition.value, {
      provider: aiTestProvider.value,
      model: aiTestModel.value?.trim() || ''
    })
    resumeId.value = data.resume_id

    // 轮询等待解析完成
    let retries = 0
    while (retries < 180) {
      await new Promise(r => setTimeout(r, 3000))
      const detail = await getResume(resumeId.value)
      syncParsingStage(detail.status)
      if (detail.status === 'completed') {
        parsedContent.value = detail.parsed_content
        analysis.value = detail.analysis
        resumeEvidence.value = detail.resume_evidence || detail.analysis?.resume_evidence || null
        evidenceSummary.value = detail.evidence_summary || resumeEvidence.value?.evidence_summary || []
        await loadKnowledgeBases()
        // 完成动画
        progress.value = 100
        parsingTitle.value = '解析完成！'
        await new Promise(r => setTimeout(r, 600))
        stopAnimations()
        step.value = 2
        return
      }
      if (detail.status === 'failed') {
        syncParsingStage('failed')
        await new Promise(r => setTimeout(r, 300))
        throw new Error(detail.error_message || '简历解析失败，请重试')
      }
      retries++
    }
    throw new Error('简历仍在后台解析中，请稍后到上传记录查看结果，无需重新上传')
  } catch (e) {
    stopAnimations()
    progress.value = 0
    parsingTitle.value = '正在上传简历...'
    error.value = e.message
    step.value = 1
  } finally {
    uploading.value = false
  }
}

function scoreColor(score) {
  if (score >= 7) return '#10b981'
  if (score >= 5) return '#f59e0b'
  return '#ef4444'
}

function percentText(value) {
  if (typeof value !== 'number') return '-'
  return `${Math.round(value * 100)}%`
}

function semanticSourceLabel(metrics) {
  if (!metrics) return 'TF-IDF 回退'
  if (metrics.semantic_backend === 'deepseek_embedding') return 'DeepSeek embedding'
  if (metrics.semantic_backend === 'openai_embedding') return 'OpenAI embedding'
  if (String(metrics.embedding_status || '').startsWith('fallback')) return 'TF-IDF 回退'
  return 'TF-IDF'
}

function parseQualityStatusLabel(status) {
  const map = {
    usable: '可用',
    low_quality: '质量偏低',
    failed: '抽取失败'
  }
  return map[status] || '待确认'
}

function parseQualityStatusClass(status) {
  if (status === 'usable') return 'ok'
  if (status === 'low_quality') return 'warn'
  if (status === 'failed') return 'bad'
  return 'unknown'
}

function parseMethodLabel(method) {
  const map = {
    pdfplumber: 'pdfplumber',
    pypdf: 'PyPDF',
    ocr_tesseract: 'OCR'
  }
  return map[method] || method || '-'
}

function parseMissingFieldLabel(field) {
  const map = {
    contact: '联系方式',
    education: '教育经历',
    projects: '项目经历',
    skills: '技能',
    experience: '工作/实习经历'
  }
  return map[field] || field
}

function parseQualityWarningLabel(value) {
  const text = String(value || '')
  if (!text) return ''
  if (text.includes('OCR fallback is disabled')) return '文本抽取质量偏低，如是扫描版简历请启用 OCR 或上传文字版 PDF。'
  if (text.includes('Contact information was not detected')) return '未识别到联系方式，不影响面试，但建议检查 PDF 文本是否完整。'
  return text
}

// 面试准备动画
const startProgress = ref(0)
const startingTitle = ref('模拟面试即将开始，请做好准备')
const startTip = ref('')
let startTipTimer = null
let startProgressTimer = null

const startTips = [
  '深呼吸，保持冷静自信 💪',
  '回答时尽量结合你的实习、社团或课程项目经历',
  '思路比答案更重要，先理清再作答',
  '不会的问题坦诚说不会，展示学习意愿',
  '自我介绍控制在1-2分钟',
  '注意条理清晰，分点作答效果更好'
]

function startStartingAnimation() {
  startProgress.value = 0
  startTip.value = startTips[0]
  let tipIdx = 0
  startTipTimer = setInterval(() => {
    tipIdx = (tipIdx + 1) % startTips.length
    startTip.value = startTips[tipIdx]
  }, 2000)

  const stages = [
    { target: 30, speed: 150, title: '模拟面试即将开始，请做好准备' },
    { target: 60, speed: 200, title: 'AI 正在生成岗位面试题目...' },
    { target: 85, speed: 350, title: '正在根据你的简历定制题目...' },
    { target: 95, speed: 600, title: '即将开始...' }
  ]
  let stageIdx = 0

  function tick() {
    if (stageIdx >= stages.length) return
    const stage = stages[stageIdx]
    if (startProgress.value < stage.target) {
      startProgress.value++
      startingTitle.value = stage.title
      startProgressTimer = setTimeout(tick, stage.speed)
    } else {
      stageIdx++
      tick()
    }
  }
  tick()
}

function stopStartingAnimation() {
  if (startTipTimer) { clearInterval(startTipTimer); startTipTimer = null }
  if (startProgressTimer) { clearTimeout(startProgressTimer); startProgressTimer = null }
}

function cacheInterviewMeta(interviewId, data) {
  const blueprint = data?.interview_blueprint || {}
  const highRiskClaims = Array.isArray(data?.high_risk_claims)
    ? data.high_risk_claims
    : Array.isArray(blueprint?.high_risk_claims)
      ? blueprint.high_risk_claims
          .map(item => (typeof item === 'object' && item ? item.claim : item))
          .filter(Boolean)
      : []
  const meta = {
    interviewId,
    interviewMode: data?.interview_mode || (multiInterviewerEnabled.value ? 'panel' : 'single'),
    totalQuestions: data?.total_questions || totalQuestions.value,
    knowledgeBaseTitle: data?.knowledge_base_title || selectedKnowledgeBase.value?.title || '',
    targetPosition: targetPosition.value,
    multiInterviewerEnabled: !!multiInterviewerEnabled.value,
    trainingFocus: Array.isArray(data?.training_focus)
      ? data.training_focus
      : (Array.isArray(blueprint?.training_focus) ? blueprint.training_focus : []),
    highRiskClaims,
    blueprintEvidenceSummary: Array.isArray(data?.blueprint_evidence_summary)
      ? data.blueprint_evidence_summary
      : (Array.isArray(blueprint?.evidence_summary) ? blueprint.evidence_summary : [])
  }
  sessionStorage.setItem(`interview_meta_${interviewId}`, JSON.stringify(meta))
  return meta
}

function buildStartErrorTips(message) {
  const text = (message || '').trim()
  if (!text) return []

  if (
    text.includes('数据库写入异常') ||
    text.includes('数据库读取或写入异常') ||
    text.includes('数据库迁移') ||
    text.includes('alembic') ||
    text.includes('UndefinedColumn') ||
    text.includes('interview_mode') ||
    text.includes('panel_snapshot') ||
    text.includes('knowledge_base_snapshot')
  ) {
    return [
      '这通常不是 API Key 问题，而是服务器数据库表结构没有跟上最新代码。',
      '请管理员在服务器执行 alembic upgrade head，并查看 docker compose logs --tail=300 app 中第一条数据库异常。'
    ]
  }

  if (text.includes('后端开始面试链路异常') || text.includes('/api/v1/interviews/start')) {
    return [
      '这说明错误发生在开始面试接口内部，不是简历分析本身的问题。',
      '请管理员查看服务器 docker compose logs --tail=300 app 中 /api/v1/interviews/start 附近的第一条异常。'
    ]
  }

  if (text.includes('API Key') || text.includes('API Token')) {
    return [
      '先在当前页面点一次“检测连接”，确认你选择的服务商和模型真的可用。',
      '如果检测失败，请去个人设置更新 API Key，或切换到另一个可用模型后再试。'
    ]
  }

  if (text.includes('Base URL') || text.includes('模型名') || text.includes('请求参数错误')) {
    return [
      '当前模型配置看起来不可用，请先检查模型名是否准确。',
      '如果你自定义了 Base URL，建议先恢复为官方默认地址后再测试。'
    ]
  }

  if (text.includes('连接') || text.includes('稍后重试')) {
    return [
      '这通常是模型服务临时不可用或响应不稳定，建议先点“检测连接”。',
      '如果你连续失败，可以切换到同服务商下的另一个模型再开始面试。'
    ]
  }

  if (text.includes('简历解析结果异常') || text.includes('简历解析结果为空')) {
    return [
      '这份简历的结构化结果可能异常，建议重新上传并重新解析一次。',
      '如果还是复现，请更换模型后重试，便于区分是数据问题还是模型返回问题。'
    ]
  }

  if (text.includes('缺少技能') || text.includes('缺少项目') || text.includes('缺少经历')) {
    return [
      '这通常是 PDF 文本抽取或结构化解析不完整导致的，不代表简历内容一定不存在。',
      '建议先查看上方“解析质量诊断”的待补字段；如果是扫描版简历，请上传文字版 PDF 或启用 OCR 后重试。'
    ]
  }

  if (text.includes('简历尚未解析完成')) {
    return [
      '简历还没有真正进入 completed 状态，请稍等几秒后重新点击开始面试。',
      '如果长时间不完成，请先回到上传页查看解析状态或失败原因。'
    ]
  }

  if (text.includes('岗位画像') || text.includes('知识库')) {
    return [
      '先改成“不使用岗位画像”再试一次，确认是否是岗位画像状态或权限问题。',
      '如果不使用岗位画像可以开始面试，再回头检查这份岗位画像是否已停用或不可见。'
    ]
  }

  if (text.includes('题目生成数量不足') || text.includes('题目生成失败')) {
    return [
      '当前模型没有稳定返回足够题目，建议先切换模型再试。',
      '也可以先把题目数量调低，或关闭“多面试官协同模式”后再验证一次。'
    ]
  }

  return [
    '建议先点“检测连接”确认当前服务商和模型可用。',
    '如果仍失败，请记录这条错误信息，便于后续继续定位开始面试链路。'
  ]
}

async function handleStart() {
  error.value = ''
  starting.value = true
  step.value = 'starting'
  startStartingAnimation()

  try {
    const data = await startInterview({
      resume_id: resumeId.value,
      target_position: targetPosition.value,
      knowledge_base_id: selectedKnowledgeBaseId.value ? Number(selectedKnowledgeBaseId.value) : null,
      ai_provider: aiTestProvider.value,
      ai_model: aiTestModel.value?.trim() || aiTestModelPlaceholder.value || null,
      difficulty: difficulty.value,
      total_questions: totalQuestions.value,
      multi_interviewer_enabled: multiInterviewerEnabled.value
    })
    const interviewMeta = cacheInterviewMeta(data.interview_id, data)
    // 完成动画
    startProgress.value = 100
    startingTitle.value = '面试准备完成！'
    stopStartingAnimation()
    await new Promise(r => setTimeout(r, 800))
    router.push({
      path: `/interview/${data.interview_id}`,
      query: {
        mode: interviewMeta.interviewMode,
        total: String(interviewMeta.totalQuestions)
      }
    })
  } catch (e) {
    stopStartingAnimation()
    error.value = e.message
    step.value = 2
  } finally {
    starting.value = false
  }
}
</script>

<style scoped>
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; font-size: 14px; font-weight: 500; color: #374151; }
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.compact-form-row {
  margin-bottom: 4px;
}
.upload-area {
  border: 2px dashed #d1d5db; border-radius: 8px; padding: 40px;
  text-align: center; cursor: pointer; transition: border-color 0.2s;
}
.upload-area:hover { border-color: #4f46e5; }
.error { color: #ef4444; font-size: 13px; margin-bottom: 12px; }
.error-tip-list {
  margin: -4px 0 12px 18px;
  padding: 0;
  color: #b45309;
  font-size: 12px;
  line-height: 1.7;
}
.parsed-info p { font-size: 14px; margin-bottom: 6px; line-height: 1.6; }
.parse-quality-card {
  margin-bottom: 20px;
  border: 1px solid #e5e7eb;
  background: #fff;
}
.parse-quality-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.parse-quality-head h3 {
  margin: 0;
  font-size: 16px;
}
.parse-quality-status {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
}
.parse-quality-status.ok { background: #dcfce7; color: #166534; }
.parse-quality-status.warn { background: #fef3c7; color: #92400e; }
.parse-quality-status.bad { background: #fee2e2; color: #991b1b; }
.parse-quality-status.unknown { background: #e5e7eb; color: #374151; }
.parse-quality-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.parse-quality-grid div {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #f9fafb;
}
.parse-quality-grid strong {
  display: block;
  font-size: 15px;
  color: #111827;
  margin-bottom: 4px;
}
.parse-quality-grid span,
.parse-quality-label {
  font-size: 12px;
  color: #6b7280;
}
.parse-quality-section {
  margin-top: 12px;
}
.parse-quality-warnings {
  margin: 12px 0 0 18px;
  padding: 0;
  color: #92400e;
  font-size: 12px;
  line-height: 1.7;
}
.api-test-card {
  border: 1px solid #e5e7eb;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}
.api-test-head {
  margin-bottom: 12px;
}
.api-test-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
}
.api-test-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.inline-msg {
  margin: 0;
}
.api-test-current-selection {
  margin: 12px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.api-test-usage-note {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}

/* 解析动画 */
.parsing-stage { text-align: center; padding: 30px 0; }
.parsing-icon { font-size: 48px; margin-bottom: 16px; animation: pulse 1.5s ease-in-out infinite; }
.ai-face-anim { margin-bottom: 16px; animation: faceFloat 2s ease-in-out infinite; }
@keyframes faceFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.7; }
}
.parsing-stage h3 { font-size: 16px; color: #374151; margin-bottom: 20px; }
.progress-bar-wrapper {
  width: 100%; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin-bottom: 8px;
}
.progress-bar {
  height: 100%; border-radius: 4px; transition: width 0.3s ease;
  background: linear-gradient(90deg, #4f46e5, #7c3aed, #a78bfa);
  background-size: 200% 100%;
  animation: shimmer 2s linear infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.progress-text { font-size: 13px; color: #6b7280; margin-bottom: 24px; }
.tips-area {
  min-height: 50px; display: flex; align-items: center; justify-content: center;
  background: #f9fafb; border-radius: 10px; padding: 14px 20px;
}
.tip-text { font-size: 13px; color: #4b5563; line-height: 1.6; margin: 0; }
.tip-fade-enter-active, .tip-fade-leave-active { transition: all 0.4s ease; }
.tip-fade-enter-from { opacity: 0; transform: translateY(8px); }
.tip-fade-leave-to { opacity: 0; transform: translateY(-8px); }

/* 分析报告 */
.analysis-card { border: 1px solid #e5e7eb; }
.evidence-card { border: 1px solid #e5e7eb; background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); }
.evidence-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
  margin-bottom: 12px;
}
.evidence-stat-tags {
  margin-bottom: 14px;
}
.evidence-stat-tag {
  background: #eef2ff;
  color: #4338ca;
}
.analysis-score { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.score-badge {
  width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; color: white; font-size: 18px; font-weight: 700;
}
.score-text { font-size: 14px; color: #6b7280; }
.matching-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.metric-item {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}
.metric-item strong {
  display: block;
  color: #111827;
  font-size: 18px;
  margin-bottom: 4px;
}
.metric-item span {
  color: #6b7280;
  font-size: 12px;
}
.semantic-source {
  display: inline-block;
  margin-top: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 11px;
  font-style: normal;
}
.metric-item.final {
  border-color: #0f766e;
  background: #ecfdf5;
}
.analysis-summary {
  font-size: 14px; line-height: 1.8; color: #374151; margin-bottom: 16px;
  padding: 10px 14px; background: #f9fafb; border-radius: 8px;
}
.analysis-section { margin-bottom: 14px; }
.analysis-actions {
  margin-bottom: 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.analysis-action-link {
  display: inline-block;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
}
.analysis-section h4 { font-size: 14px; margin-bottom: 8px; color: #374151; }
.learning-task-bridge {
  padding: 12px;
  border: 1px solid #d1fae5;
  border-radius: 8px;
  background: #f0fdf4;
}
.learning-task-bridge p {
  color: #4b5563;
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 10px;
}
.learning-task-message {
  color: #047857 !important;
  margin-bottom: 0 !important;
}
.ability-gap-section {
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}
.ability-gap-list {
  display: grid;
  gap: 10px;
}
.ability-gap-item {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}
.ability-gap-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}
.ability-gap-head strong {
  color: #111827;
  font-size: 13px;
}
.ability-gap-head span {
  color: #1d4ed8;
  font-size: 12px;
  white-space: nowrap;
}
.ability-gap-meta,
.ability-gap-item p {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.7;
}
.ability-gap-item p {
  margin-top: 4px;
}
.tag-list { display: flex; flex-wrap: wrap; gap: 8px; }
.tag { padding: 3px 10px; border-radius: 12px; font-size: 12px; }
.tag-green { background: #d1fae5; color: #065f46; }
.tag-red { background: #fee2e2; color: #991b1b; }
.evidence-status {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px !important;
  font-weight: 600;
}
.evidence-status-direct { color: #065f46 !important; background: #d1fae5; }
.evidence-status-indirect { color: #1d4ed8 !important; background: #dbeafe; }
.evidence-status-claimed_only,
.evidence-status-needs_verification { color: #92400e !important; background: #fef3c7; }
.evidence-status-missing { color: #991b1b !important; background: #fee2e2; }
.evidence-status-hint {
  color: #92400e !important;
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  padding: 6px 8px;
  border-radius: 6px;
}
.analysis-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 14px; }
.analysis-two-col ul, .analysis-section ul { list-style: none; padding: 0; }
.analysis-two-col li, .analysis-section li {
  font-size: 13px; line-height: 1.8; padding-left: 14px; position: relative;
}
.analysis-two-col li::before, .analysis-section li::before {
  content: '•'; position: absolute; left: 0; color: #9ca3af;
}
.knowledge-card {
  border: 1px solid #e5e7eb;
}
.knowledge-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.knowledge-desc {
  color: #6b7280;
  font-size: 14px;
  line-height: 1.7;
}
.knowledge-loading,
.knowledge-empty {
  font-size: 14px;
  color: #6b7280;
}
.knowledge-preview {
  margin-top: 14px;
  padding: 14px;
  border-radius: 10px;
  background: #f9fafb;
}
.knowledge-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.knowledge-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ede9fe;
  color: #5b21b6;
  font-size: 12px;
  font-weight: 600;
}
.knowledge-tag.subtle {
  background: #e5e7eb;
  color: #4b5563;
}
.knowledge-tag.public-tag {
  background: #dbeafe;
  color: #1d4ed8;
}
.knowledge-tag.private-tag {
  background: #ede9fe;
  color: #5b21b6;
}
.knowledge-preview-text,
.knowledge-detail {
  font-size: 14px;
  color: #374151;
  line-height: 1.8;
}
.knowledge-detail {
  margin-top: 10px;
}
.panel-mode-card {
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(16, 185, 129, 0.08));
  border: 1px solid rgba(79, 70, 229, 0.12);
}
.panel-mode-toggle {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}
.panel-mode-toggle input {
  margin-top: 4px;
}
.panel-mode-toggle strong {
  display: block;
  font-size: 14px;
  color: #111827;
  margin-bottom: 4px;
}
.panel-mode-toggle small {
  display: block;
  font-size: 12px;
  line-height: 1.6;
  color: #4b5563;
}
.panel-mode-preview {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(79, 70, 229, 0.08);
}
.panel-preview-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.panel-preview-label {
  font-size: 12px;
  font-weight: 600;
  color: #4338ca;
  padding-top: 2px;
  white-space: nowrap;
}
.panel-preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.panel-preview-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #374151;
  background: #eef2ff;
  border: 1px solid rgba(79, 70, 229, 0.1);
}
.panel-preview-note {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #4b5563;
}
@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }
  .matching-metrics {
    grid-template-columns: 1fr 1fr;
  }
  .api-test-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

