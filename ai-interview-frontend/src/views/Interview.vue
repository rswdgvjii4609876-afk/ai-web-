<template>
  <div class="interview-page">
    <div v-if="preparing" class="prepare-overlay">
      <div class="prepare-card">
        <div class="ai-face-large">
          <svg viewBox="0 0 80 80" width="80" height="80">
            <circle cx="40" cy="40" r="38" fill="white" stroke="#4f46e5" stroke-width="2" />
            <ellipse cx="28" cy="36" rx="5" ry="6" fill="#1e1e1e">
              <animate attributeName="ry" values="6;1;6" dur="2.5s" repeatCount="indefinite" />
            </ellipse>
            <ellipse cx="52" cy="36" rx="5" ry="6" fill="#1e1e1e">
              <animate attributeName="ry" values="6;1;6" dur="2.5s" repeatCount="indefinite" />
            </ellipse>
            <path d="M30 52 Q40 60 50 52" stroke="#1e1e1e" stroke-width="2" fill="none" stroke-linecap="round" />
          </svg>
        </div>
        <h2 class="prepare-title">模拟面试即将开始</h2>
        <p class="prepare-tip">{{ prepareTip }}</p>
        <div class="prepare-progress">
          <div class="prepare-bar" :style="{ width: `${preparePercent}%` }"></div>
        </div>
        <p class="prepare-subtitle">AI 正在结合简历证据和岗位画像准备题目...</p>
      </div>
    </div>

    <div v-if="!preparing" class="interview-header">
      <div class="header-brand">
        <svg viewBox="0 0 32 32" width="24" height="24">
          <circle cx="16" cy="16" r="15" fill="white" stroke="#4f46e5" stroke-width="1.5" />
          <ellipse cx="11" cy="14" rx="2.5" ry="3" fill="#1e1e1e" />
          <ellipse cx="21" cy="14" rx="2.5" ry="3" fill="#1e1e1e" />
        </svg>
        <span>职启智评面试官</span>
      </div>
      <span class="progress">第 {{ currentIndex + 1 }} / {{ totalQuestions }} 题</span>
      <router-link
        to="/dashboard"
        class="btn-secondary"
        style="padding:4px 12px;font-size:12px;border-radius:6px;display:inline-block"
      >
        退出
      </router-link>
    </div>

    <div v-if="!preparing && loadError" class="interview-load-error card">
      <h2>面试记录暂时无法打开</h2>
      <p>{{ safeText(loadError) }}</p>
      <div class="load-error-actions">
        <button type="button" class="btn-secondary" @click="reloadMessages">重试</button>
        <router-link to="/dashboard" class="btn-secondary">返回工作台</router-link>
        <router-link v-if="loadErrorIsAiConfig" to="/profile" class="btn-primary">检查 AI 调用设置</router-link>
      </div>
    </div>

    <div v-if="!preparing && !loadError && hasBlueprintCard" class="blueprint-card">
      <div class="blueprint-card-top">
        <div>
          <strong>当前训练重点</strong>
          <p class="blueprint-card-note">首轮提问和后续追问会优先围绕这些缺口与高风险点展开。</p>
        </div>
        <span class="blueprint-mode-chip">{{ interviewModeLabel }}</span>
      </div>
      <ul v-if="trainingFocus.length" class="blueprint-list">
        <li v-for="item in trainingFocus" :key="`focus-${item}`">{{ safeText(item) }}</li>
      </ul>
      <div v-if="highRiskClaims.length" class="blueprint-risk-block">
        <p class="blueprint-subtitle">当前高风险点</p>
        <ul class="blueprint-list compact">
          <li v-for="item in highRiskClaims" :key="`risk-${item}`">{{ safeText(item) }}</li>
        </ul>
      </div>
      <p v-if="blueprintEvidenceSummary.length" class="blueprint-evidence">
        证据摘要：{{ safeJoin(blueprintEvidenceSummary) }}
      </p>
    </div>

    <div v-if="!preparing && !loadError && isPanelMode" class="panel-status-card">
      <div class="panel-status-top">
        <div>
          <strong>当前模式：多角色协同评估</strong>
          <p class="panel-status-note">
            对外仍然是单主持人提问；内部会综合岗位画像、简历证据、表达逻辑和改进潜力做选题、追问和评估。
          </p>
        </div>
        <span class="panel-status-chip">内部协同中</span>
      </div>
      <div class="panel-role-tags">
        <span v-for="item in panelRoleHints" :key="item" class="panel-role-tag">{{ item }}</span>
      </div>
      <details v-if="latestRoundSummary" class="round-summary">
        <summary>最近一轮内部评估</summary>
        <p v-if="latestRoundSummary.feedback" class="round-summary-feedback">
          {{ safeText(latestRoundSummary.feedback) }}
        </p>
        <ul v-if="latestRoundSummary.points.length" class="round-summary-list">
          <li v-for="(item, index) in latestRoundSummary.points" :key="`${item}-${index}`">{{ safeText(item) }}</li>
        </ul>
      </details>
    </div>

    <div v-if="!preparing && !loadError" ref="chatArea" class="chat-area">
      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div v-if="msg.role === 'interviewer'" class="avatar-col">
          <svg viewBox="0 0 40 40" width="36" height="36" class="ai-avatar">
            <circle cx="20" cy="20" r="19" fill="white" stroke="#e5e7eb" stroke-width="1" />
            <ellipse cx="14" cy="17" rx="2.5" ry="3" fill="#1e1e1e" />
            <ellipse cx="26" cy="17" rx="2.5" ry="3" fill="#1e1e1e" />
          </svg>
        </div>

        <div class="bubble">
          <div class="bubble-content" v-text="renderContent(msg.content)"></div>
          <div v-if="msg.score" class="bubble-score">评分 {{ msg.score }}/10</div>
        </div>

        <div v-if="msg.role === 'candidate'" class="avatar-col">
          <img
            v-if="userAvatar && !avatarError"
            :src="userAvatar"
            class="user-avatar"
            alt="me"
            @error="avatarError = true"
          />
          <div v-else class="user-avatar-placeholder">{{ userInitial }}</div>
        </div>
      </div>

      <div v-if="streamingText" class="message interviewer">
        <div class="avatar-col">
          <svg viewBox="0 0 40 40" width="36" height="36" class="ai-avatar thinking">
            <circle cx="20" cy="20" r="19" fill="white" stroke="#4f46e5" stroke-width="1.5" />
            <ellipse cx="14" cy="17" rx="2.5" ry="3" fill="#1e1e1e">
              <animate attributeName="ry" values="3;1;3" dur="1.5s" repeatCount="indefinite" />
            </ellipse>
            <ellipse cx="26" cy="17" rx="2.5" ry="3" fill="#1e1e1e">
              <animate attributeName="ry" values="3;1;3" dur="1.5s" repeatCount="indefinite" />
            </ellipse>
          </svg>
        </div>
        <div class="bubble">
          <div class="bubble-content streaming-content" v-text="renderContent(streamingText)"></div>
          <span class="cursor-blink">▌</span>
        </div>
      </div>

      <div v-if="thinking && !streamingText" class="message interviewer">
        <div class="avatar-col">
          <svg viewBox="0 0 40 40" width="36" height="36" class="ai-avatar thinking">
            <circle cx="20" cy="20" r="19" fill="white" stroke="#4f46e5" stroke-width="1.5" />
            <ellipse cx="14" cy="17" rx="2.5" ry="3" fill="#1e1e1e">
              <animate attributeName="ry" values="3;1;3" dur="1s" repeatCount="indefinite" />
            </ellipse>
            <ellipse cx="26" cy="17" rx="2.5" ry="3" fill="#1e1e1e">
              <animate attributeName="ry" values="3;1;3" dur="1s" repeatCount="indefinite" />
            </ellipse>
          </svg>
        </div>
        <div class="bubble thinking-bubble">
          <span class="dot-animation">AI 思考中<span class="dots"></span></span>
        </div>
      </div>
    </div>

    <div
      v-if="!preparing && !loadError && latestRoundSummary && !roundSummaryDismissed"
      class="round-feedback-panel"
    >
      <div class="round-feedback-bar">
        <div class="round-feedback-main">
          <strong>上一题评分 {{ roundSummaryScoreText }}</strong>
          <span>{{ safeText(latestRoundSummary.questionTargetGap || latestRoundSummary.feedback || '本轮评估已完成，可以继续回答下一题。') }}</span>
        </div>
        <div class="round-feedback-actions">
          <button
            class="round-feedback-btn"
            type="button"
            :aria-expanded="roundSummaryExpanded"
            @click="roundSummaryExpanded = !roundSummaryExpanded"
          >
            {{ roundSummaryExpanded ? '收起详情' : '查看详情' }}
          </button>
          <button class="round-feedback-close" type="button" aria-label="关闭本轮评分反馈" @click="roundSummaryDismissed = true">
            ×
          </button>
        </div>
      </div>
      <div v-if="roundSummaryExpanded" class="round-feedback-detail">
        <p v-if="latestRoundSummary.questionReason" class="round-loop-feedback">
          {{ safeText(latestRoundSummary.questionReason) }}
        </p>
        <div class="round-loop-grid">
          <div v-if="latestRoundSummary.questionTargetGap" class="round-loop-block">
            <p class="round-loop-title">当前验证缺口</p>
            <p class="round-loop-text">{{ safeText(latestRoundSummary.questionTargetGap) }}</p>
          </div>
          <div v-if="latestRoundSummary.questionTargetEvidence.length" class="round-loop-block">
            <p class="round-loop-title">当前证据目标</p>
            <ul class="round-loop-list">
              <li
                v-for="(item, index) in latestRoundSummary.questionTargetEvidence"
                :key="`question-target-${item}-${index}`"
              >
                {{ safeText(item) }}
              </li>
            </ul>
          </div>
          <div v-if="latestRoundSummary.unresolvedGaps.length" class="round-loop-block">
            <p class="round-loop-title">仍待澄清</p>
            <ul class="round-loop-list">
              <li v-for="(item, index) in latestRoundSummary.unresolvedGaps" :key="`gap-${item}-${index}`">
                {{ safeText(item) }}
              </li>
            </ul>
          </div>
          <div v-if="latestRoundSummary.evidenceStrengthDelta.length" class="round-loop-block">
            <p class="round-loop-title">证据强度变化</p>
            <ul class="round-loop-list">
              <li
                v-for="(item, index) in latestRoundSummary.evidenceStrengthDelta"
                :key="`delta-${index}`"
              >
                {{ safeText(item.evidence) }}：{{ formatDeltaLabel(item.delta) }}
                <span v-if="item.reason" class="round-loop-inline-note">（{{ safeText(item.reason) }}）</span>
              </li>
            </ul>
          </div>
          <div v-if="latestRoundSummary.claimConfidenceChange.length" class="round-loop-block">
            <p class="round-loop-title">高风险表述置信度</p>
            <ul class="round-loop-list">
              <li
                v-for="(item, index) in latestRoundSummary.claimConfidenceChange"
                :key="`claim-${index}`"
              >
                {{ safeText(item.claim) }}：{{ formatConfidenceLevel(item.from_level) }} -> {{ formatConfidenceLevel(item.to_level) }}
              </li>
            </ul>
          </div>
          <div v-if="latestRoundSummary.nextBestFollowup" class="round-loop-block">
            <p class="round-loop-title">下一步最佳追问</p>
            <p class="round-loop-text">{{ safeText(latestRoundSummary.nextBestFollowup.question) }}</p>
            <p v-if="latestRoundSummary.nextBestFollowup.reason" class="round-loop-inline-note">
              {{ safeText(latestRoundSummary.nextBestFollowup.reason) }}
            </p>
            <p
              v-if="latestRoundSummary.nextBestFollowup.evidenceSourceSummary?.length"
              class="round-loop-inline-note"
            >
              证据来源：{{ safeJoin(latestRoundSummary.nextBestFollowup.evidenceSourceSummary) }}
            </p>
          </div>
        </div>
        <ul v-if="latestRoundSummary.points.length" class="round-summary-list compact">
          <li v-for="(item, index) in latestRoundSummary.points" :key="`round-point-${index}`">{{ safeText(item) }}</li>
        </ul>
      </div>
    </div>

    <AiConfigErrorNotice v-if="!preparing && !loadError && streamError" :error="safeText(streamError)" class="interview-error-notice" />

    <div v-if="!preparing && !loadError && !finished" class="input-area">
      <textarea
        v-model="answer"
        placeholder="输入你的回答..."
        rows="3"
        :disabled="thinking"
        @keydown.enter.exact.prevent="handleSubmit"
        @keydown.shift.enter.exact="null"
      ></textarea>
      <button class="btn-primary" :disabled="!answer.trim() || thinking" @click="handleSubmit">
        {{ thinking ? '评估中...' : '发送 (Enter)' }}
      </button>
    </div>

    <div v-if="!preparing && !loadError && finished" class="input-area finished">
      <p>面试已结束</p>
      <router-link
        :to="`/interview/${interviewId}/report`"
        class="btn-primary"
        style="display:inline-block;padding:10px 24px;color:white;border-radius:8px"
      >
        查看评估报告
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getMessages, submitAnswerStream } from '../api/interview'
import AiConfigErrorNotice from '../components/AiConfigErrorNotice.vue'
import { isAiConfigError } from '../utils/aiConfigError'

const route = useRoute()
const authStore = useAuthStore()
const interviewId = route.params.id

const messages = ref([])
const answer = ref('')
const thinking = ref(false)
const finished = ref(false)
const currentIndex = ref(0)
const totalQuestions = ref(5)
const chatArea = ref(null)
const streamingText = ref('')
const streamError = ref('')
const loadError = ref('')
const latestRoundSummary = ref(null)
const roundSummaryExpanded = ref(false)
const roundSummaryDismissed = ref(true)
const interviewMeta = ref(null)
const loadErrorIsAiConfig = computed(() => isAiConfigError(loadError.value))
const panelRoleHints = ['岗位匹配', '经历追问', '沟通表达', '证据核查', '改进建议']

const preparing = ref(true)
const preparePercent = ref(0)
const prepareTips = [
  '请做好准备，保持冷静和自信',
  '回答时尽量结合你的实习、社团或课程项目经历',
  '注意条理清晰，分点作答',
  '面试官会根据你的简历证据继续追问'
]
const prepareTip = ref(prepareTips[0])

const userAvatar = computed(() => authStore.userAvatar || '')
const avatarError = ref(false)
const userInitial = computed(() => {
  const name = authStore.userName || ''
  return name.charAt(0).toUpperCase() || '我'
})
const interviewMode = computed(() => interviewMeta.value?.interviewMode || route.query.mode || 'single')
const isPanelMode = computed(() => interviewMode.value === 'panel')
const trainingFocus = computed(() => {
  const items = interviewMeta.value?.trainingFocus
  return Array.isArray(items) ? items.slice(0, 3) : []
})
const highRiskClaims = computed(() => {
  const items = interviewMeta.value?.highRiskClaims
  return Array.isArray(items) ? items.slice(0, 3) : []
})
const blueprintEvidenceSummary = computed(() => {
  const items = interviewMeta.value?.blueprintEvidenceSummary
  return Array.isArray(items) ? items.slice(0, 3) : []
})
const hasBlueprintCard = computed(() => {
  return trainingFocus.value.length || highRiskClaims.value.length || blueprintEvidenceSummary.value.length
})
const interviewModeLabel = computed(() => {
  return interviewMode.value === 'panel' ? '多角色协同评估' : '单面试官模式'
})
const roundSummaryScoreText = computed(() => {
  const value = latestRoundSummary.value?.score
  if (value === null || value === undefined || value === '') return '-/10'
  const score = Number(value)
  return Number.isFinite(score) ? `${score.toFixed(1)}/10` : `${value}/10`
})

function loadInterviewMeta() {
  const storageKey = `interview_meta_${interviewId}`
  let storedMeta = null
  try {
    storedMeta = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
  } catch (e) {
    storedMeta = null
  }

  const queryMode = typeof route.query.mode === 'string' ? route.query.mode : ''
  const queryTotal = Number(route.query.total || 0)
  interviewMeta.value = {
    ...(storedMeta || {}),
    interviewMode: queryMode || storedMeta?.interviewMode || 'single',
    totalQuestions: queryTotal || storedMeta?.totalQuestions || totalQuestions.value
  }

  if (interviewMeta.value.totalQuestions) {
    totalQuestions.value = Number(interviewMeta.value.totalQuestions)
  }
}

function hydrateMessages(data) {
  const msgList = Array.isArray(data) ? data : (data?.items || data || [])
  const safeList = Array.isArray(msgList) ? msgList : []
  if (!Array.isArray(data) && data && typeof data === 'object') {
    if (Number.isInteger(Number(data.total_questions)) && Number(data.total_questions) > 0) {
      totalQuestions.value = Number(data.total_questions)
    }
    if (Number.isInteger(Number(data.current_question_index)) && Number(data.current_question_index) >= 0) {
      currentIndex.value = Number(data.current_question_index)
    }
    if (data.status === 'completed') {
      finished.value = true
    }
  }
  messages.value = safeList.map(item => ({
    role: item.role,
    content: item.content,
    score: item.score,
    feedback: item.feedback
  }))
  const latestScored = [...safeList]
    .reverse()
    .find(item => item.role === 'candidate' && ((item.score !== null && item.score !== undefined) || item.feedback))
  if (latestScored) {
    latestRoundSummary.value = normalizeRoundSummary({
      score: latestScored.score,
      feedback: latestScored.feedback || '上一轮回答已有评分反馈。',
      evidence_summary: [],
      unresolved_gaps: [],
      evidence_strength_delta: [],
      claim_confidence_change: [],
      question_target_evidence: []
    })
    roundSummaryExpanded.value = false
    roundSummaryDismissed.value = false
  } else {
    latestRoundSummary.value = null
    roundSummaryExpanded.value = false
    roundSummaryDismissed.value = true
  }
  const indices = safeList.map(item => item.question_index).filter(index => index != null)
  if (indices.length && !finished.value) {
    currentIndex.value = Math.max(...indices)
  }
  if (currentIndex.value >= totalQuestions.value) {
    finished.value = true
  }
  return safeList
}

function normalizeRoundSummary(data) {
  if (!data) return null

  const moderator = data.moderator || {}
  const metadata = data.metadata || {}
  const panelViews = Array.isArray(data.panel_views) ? data.panel_views : []
  const followups = moderator.selected_followups || data.selected_followups || []
  const sliceIds = metadata.retrieved_slice_ids || data.used_slice_ids || []
  const roundEvidenceSummary = Array.isArray(data.evidence_summary) ? data.evidence_summary : []
  const unresolvedGaps = Array.isArray(data.unresolved_gaps) ? data.unresolved_gaps : []
  const evidenceStrengthDelta = Array.isArray(data.evidence_strength_delta) ? data.evidence_strength_delta : []
  const claimConfidenceChange = Array.isArray(data.claim_confidence_change) ? data.claim_confidence_change : []
  const questionTargetEvidence = Array.isArray(data.question_target_evidence) ? data.question_target_evidence : []
  const nextBestFollowup =
    data.next_best_followup && typeof data.next_best_followup === 'object' ? data.next_best_followup : null
  const points = []

  panelViews.slice(0, 3).forEach(item => {
    if (!item || typeof item !== 'object' || !item.summary) return
    points.push(`${item.title || item.role || '协同视角'}：${item.summary}`)
  })

  if (followups.length) {
    points.push(`建议追问：${followups.slice(0, 2).join('；')}`)
  }
  if (sliceIds.length) {
    points.push(`参考切片：#${sliceIds.slice(0, 4).join(' / #')}`)
  }
  const evidenceSummary = Array.isArray(data.evidence_summary) ? data.evidence_summary : []
  evidenceSummary.slice(0, 2).forEach(item => {
    if (item) points.push(`训练依据：${item}`)
  })
  if (nextBestFollowup?.question) {
    points.push(`下一步：${nextBestFollowup.question}`)
  }
  if (!points.length) {
    points.push('本轮回答已完成多视角内部评估，结果会汇总到最终报告。')
  }

  return {
    feedback: data.feedback || moderator.reasoning_summary || '',
    score: data.score ?? null,
    modeLabel: isPanelMode.value ? '证据追问闭环' : '单面试官闭环',
    questionTargetGap: data.question_target_gap || '',
    questionTargetEvidence: questionTargetEvidence.slice(0, 4),
    questionReason: data.question_reason || '',
    unresolvedGaps: unresolvedGaps.slice(0, 4),
    evidenceStrengthDelta: evidenceStrengthDelta.slice(0, 4),
    claimConfidenceChange: claimConfidenceChange.slice(0, 3),
    nextBestFollowup,
    blueprintEvidenceSummary: roundEvidenceSummary.slice(0, 2),
    points
  }
}

function formatDeltaLabel(delta) {
  const map = {
    strengthened: '已补强',
    increased: '明显增强',
    weakened: '仍然偏弱',
    insufficient: '证据不足',
    unchanged: '变化有限'
  }
  return map[delta] || '变化有限'
}

function formatConfidenceLevel(level) {
  const map = {
    direct: 'direct',
    indirect: 'indirect',
    claimed_only: 'claimed_only',
    missing: 'missing',
    high: 'high',
    medium: 'medium',
    low: 'low',
    unknown: 'unknown'
  }
  return map[level] || 'unknown'
}

function hasInternalPromptLeak(text) {
  const value = String(text || '')
  return /Blueprint\s+priority|blueprint[_\s-]*track|blueprint[_\s-]*priority|role[_\s-]*calibration|Assess\s+boundary|Place\s+the\s+candidate|Question\s+plan|Question\s+reason|Question\s+target\s+gap|Evaluation\s+focus|Interview\s+routing\s+context|Interview\s+blueprint|Internal\s+panel|Internal\s+roles|Moderator\s+name|Plan\s*#|Lead\s+role|Support\s+roles|Requirement\s+status|Candidate\s+evidence|Suggested\s+followups|question_plan|candidate_evidence|verification_reason|stage\/category\/intent|lead_role|support_roles|assessment_points|selected_questions|used_slice_ids|routed[_\s-]*slice|routed\s+slices|evaluation_focus|selected_followups|chain[-\s]?of[-\s]?thought|Use\s+the\s+self[-\s]?introduction|Deep[-\s]?dive\s+the\s+most\s+important\s+project|Validate\s+mastery\s+of\s+core\s+knowledge|Evaluate\s+collaboration|Use\s+debugging\s+or\s+optimization|Further\s+verify\s+role\s+boundaries|Use\s+business\s+changes|Close\s+the\s+interview|Probe\s+technical\s+depth|\b(stage|category|intent|moderator|schema|step|type|goal|priority|focus|blueprint)\b\s*[:=]/i.test(value)
}

function renderContent(text) {
  if (!text) return ''
  if (hasInternalPromptLeak(text)) {
    return '题目生成异常：系统已拦截内部调试信息，请刷新页面或重新开始面试。'
  }
  return String(text)
    .replace(/```json\s*\{[\s\S]*?\}\s*```/g, '')
    .replace(/\{[^{}]*"score"\s*:\s*[\d.]+[^{}]*\}/g, '')
    .trim()
}

function safeText(text) {
  return renderContent(text)
}

function safeJoin(items, separator = '；') {
  if (!Array.isArray(items)) return ''
  return items.map((item) => safeText(item)).filter(Boolean).join(separator)
}

function scrollToBottom() {
  nextTick(() => {
    if (chatArea.value) {
      chatArea.value.scrollTop = chatArea.value.scrollHeight
    }
  })
}

async function reloadMessages() {
  try {
    const data = await getMessages(interviewId)
    loadError.value = ''
    hydrateMessages(data)
    nextTick(scrollToBottom)
  } catch (e) {
    console.error('加载消息失败:', e)
    loadError.value = e.message || '面试记录不存在、已被删除，或当前账号无权访问。'
  }
}

onMounted(async () => {
  loadInterviewMeta()

  let tipIdx = 0
  const tipTimer = setInterval(() => {
    tipIdx = (tipIdx + 1) % prepareTips.length
    prepareTip.value = prepareTips[tipIdx]
  }, 1500)

  const barTimer = setInterval(() => {
    if (preparePercent.value < 90) preparePercent.value += 2
  }, 100)

  await reloadMessages()

  preparePercent.value = 100
  clearInterval(barTimer)
  clearInterval(tipTimer)
  setTimeout(() => {
    preparing.value = false
  }, 600)
  nextTick(scrollToBottom)
})

async function handleSubmit() {
  if (!answer.value.trim() || thinking.value) return

  const myAnswer = answer.value.trim()
  answer.value = ''
  const optimisticMessage = { role: 'candidate', content: myAnswer, pending: true }
  messages.value.push(optimisticMessage)
  scrollToBottom()
  thinking.value = true
  streamingText.value = ''
  streamError.value = ''
  roundSummaryExpanded.value = false
  roundSummaryDismissed.value = true
  let rawStreamText = ''

  try {
    await submitAnswerStream(
      interviewId,
      myAnswer,
      currentIndex.value,
      chunk => {
        rawStreamText += chunk
        let display = rawStreamText
          .replace(/```json\s*\{[\s\S]*?\}\s*```/g, '')
          .replace(/\{[^{}]*"score"\s*:\s*[\d.]+[^{}]*\}/g, '')
        display = display.replace(/```json[\s\S]*$/g, '')
        display = display.replace(/\{[^}]*$/g, match => {
          return /["']?score/.test(match) || /^\{\s*$/.test(match) ? '' : match
        })
        streamingText.value = display.trim()
        scrollToBottom()
      },
      data => {
        latestRoundSummary.value = normalizeRoundSummary(data)
        roundSummaryExpanded.value = false
        roundSummaryDismissed.value = false

        if (rawStreamText.trim()) {
          const displayText = rawStreamText
            .replace(/```json\s*\{[\s\S]*?\}\s*```/g, '')
            .replace(/\{[^{}]*"score"\s*:\s*[\d.]+[^{}]*\}/g, '')
            .trim()
          if (displayText) {
            messages.value.push({ role: 'interviewer', content: displayText, score: data.score })
          }
        }

        streamingText.value = ''
        rawStreamText = ''

        const lastCandidate = [...messages.value].reverse().find(item => item.role === 'candidate')
        if (lastCandidate) {
          lastCandidate.score = data.score
        }

        if (data.is_finished) {
          finished.value = true
        } else if (data.next_question) {
          currentIndex.value = data.question_index + 1
          messages.value.push({ role: 'interviewer', content: data.next_question })
        }
        scrollToBottom()
      }
    )
  } catch (e) {
    streamingText.value = ''
    streamError.value = e.message || '回答提交失败'
    const optimisticIndex = messages.value.indexOf(optimisticMessage)
    if (optimisticIndex >= 0) {
      messages.value.splice(optimisticIndex, 1)
    }
    try {
      const data = await getMessages(interviewId)
      hydrateMessages(data)
    } catch (refreshError) {
      console.error('Refresh interview messages after stream failure failed:', refreshError)
    }
    messages.value.push({ role: 'interviewer', content: `出错了：${safeText(streamError.value)}` })
    scrollToBottom()
  } finally {
    thinking.value = false
  }
}
</script>

<style scoped>
.interview-page {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 73px);
  min-height: 520px;
  max-width: 800px;
  margin: 0 auto;
}

.interview-load-error {
  margin: 18px 20px;
  padding: 24px;
}

.interview-load-error h2 {
  font-size: 18px;
  margin-bottom: 8px;
  color: #111827;
}

.interview-load-error p {
  color: #6b7280;
  line-height: 1.7;
}

.load-error-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.interview-error-notice {
  flex-shrink: 0;
  margin: 8px 16px;
}

.prepare-overlay {
  position: fixed;
  inset: 0;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.prepare-card {
  text-align: center;
  padding: 40px;
}

.ai-face-large {
  animation: faceFloat 2s ease-in-out infinite;
}

@keyframes faceFloat {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

.prepare-title {
  margin-top: 20px;
  font-size: 20px;
}

.prepare-tip {
  color: #6b7280;
  margin-top: 8px;
  font-size: 14px;
}

.prepare-subtitle {
  color: #9ca3af;
  font-size: 12px;
  margin-top: 8px;
}

.prepare-progress {
  width: 280px;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  margin: 16px auto 0;
  overflow: hidden;
}

.prepare-bar {
  height: 100%;
  background: linear-gradient(90deg, #4f46e5, #7c3aed);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.interview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  font-size: 14px;
  font-weight: 600;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress {
  color: #6b7280;
  font-weight: 400;
}

.blueprint-card {
  margin: 16px 20px 0;
  padding: 14px 16px;
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.blueprint-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.blueprint-card-note {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
}

.blueprint-mode-chip {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 600;
}

.blueprint-list {
  margin: 12px 0 0 18px;
  padding: 0;
  color: #374151;
  font-size: 13px;
  line-height: 1.7;
}

.blueprint-list.compact {
  margin-top: 8px;
}

.blueprint-risk-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eef2ff;
}

.blueprint-subtitle {
  font-size: 13px;
  font-weight: 600;
  color: #312e81;
}

.blueprint-evidence {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.panel-status-card {
  margin: 16px 20px 0;
  padding: 14px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(16, 185, 129, 0.08));
  border: 1px solid rgba(79, 70, 229, 0.1);
}

.panel-status-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-status-note {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #4b5563;
}

.panel-status-chip {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 600;
}

.panel-role-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.panel-role-tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(79, 70, 229, 0.08);
  color: #374151;
  font-size: 12px;
}

.round-summary {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(79, 70, 229, 0.08);
}

.round-summary summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #312e81;
}

.round-summary-feedback {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}

.round-summary-list {
  list-style: none;
  padding: 0;
  margin: 10px 0 0;
}

.round-summary-list li {
  position: relative;
  padding-left: 14px;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #4b5563;
}

.round-summary-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #6d28d9;
}

.round-summary-list.compact {
  margin-top: 14px;
}

.round-loop-feedback {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #1f2937;
}

.round-loop-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.round-loop-block {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(14, 165, 233, 0.12);
}

.round-loop-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.round-loop-text {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}

.round-loop-list {
  margin: 8px 0 0 16px;
  padding: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}

.round-loop-inline-note {
  margin-top: 6px;
  display: block;
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
}

.chat-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.round-feedback-panel {
  flex-shrink: 0;
  margin: 0 20px 10px;
  border: 1px solid rgba(14, 165, 233, 0.16);
  border-radius: 12px;
  background: #f8fbff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.round-feedback-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
}

.round-feedback-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #1f2937;
  font-size: 13px;
}

.round-feedback-main strong {
  flex-shrink: 0;
  color: #0f172a;
}

.round-feedback-main span {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: #4b5563;
}

.round-feedback-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.round-feedback-btn,
.round-feedback-close {
  border: 0;
  cursor: pointer;
  font-family: inherit;
}

.round-feedback-btn {
  padding: 6px 10px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  font-weight: 700;
}

.round-feedback-close {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #eef2ff;
  color: #4b5563;
  font-size: 18px;
  line-height: 1;
}

.round-feedback-detail {
  max-height: 30vh;
  overflow-y: auto;
  padding: 0 12px 12px;
  border-top: 1px solid rgba(14, 165, 233, 0.12);
}

.message {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.message.interviewer {
  justify-content: flex-start;
}

.message.candidate {
  justify-content: flex-end;
}

.avatar-col {
  flex-shrink: 0;
  margin-top: 2px;
}

.ai-avatar {
  border-radius: 50%;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
}

.ai-avatar.thinking {
  animation: avatarPulse 1.5s ease-in-out infinite;
}

@keyframes avatarPulse {
  0%,
  100% {
    filter: drop-shadow(0 0 0 rgba(79, 70, 229, 0));
  }
  50% {
    filter: drop-shadow(0 0 8px rgba(79, 70, 229, 0.4));
  }
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
}

.user-avatar-placeholder {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.interviewer .bubble {
  background: white;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 4px;
}

.candidate .bubble {
  background: #4f46e5;
  color: white;
  border-bottom-right-radius: 4px;
}

.bubble-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.thinking-bubble {
  color: #6b7280;
  font-style: italic;
}

.dot-animation .dots::after {
  content: '';
  animation: dots 1.5s steps(4, end) infinite;
}

@keyframes dots {
  0% {
    content: '';
  }
  25% {
    content: '.';
  }
  50% {
    content: '..';
  }
  75% {
    content: '...';
  }
  100% {
    content: '';
  }
}

.streaming-content {
  display: inline;
}

.cursor-blink {
  display: inline;
  animation: blink 0.8s step-end infinite;
  color: #4f46e5;
  font-size: 14px;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.bubble-score {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  font-size: 13px;
}

.interviewer .bubble-score {
  border-top-color: #e5e7eb;
}

.input-area {
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-area textarea {
  flex: 1;
  resize: none;
  font-family: inherit;
}

.input-area.finished {
  justify-content: center;
  align-items: center;
  padding: 24px;
  gap: 16px;
}

.input-area.finished p {
  font-size: 18px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .interview-page {
    height: calc(100dvh - 122px);
    min-height: 460px;
  }

  .interview-header {
    gap: 10px;
    flex-wrap: wrap;
  }

  .panel-status-top {
    flex-direction: column;
  }

  .bubble {
    max-width: 82%;
  }

  .input-area {
    flex-direction: column;
    align-items: stretch;
  }

  .round-feedback-panel {
    margin: 0 12px 8px;
  }

  .round-feedback-bar,
  .round-feedback-main {
    align-items: flex-start;
  }

  .round-feedback-bar {
    flex-direction: column;
  }

  .round-feedback-main {
    width: 100%;
    flex-direction: column;
    gap: 4px;
  }

  .round-feedback-main span {
    white-space: normal;
  }

  .round-feedback-actions {
    width: 100%;
    justify-content: space-between;
  }

  .round-feedback-detail {
    max-height: 25vh;
  }
}
</style>
