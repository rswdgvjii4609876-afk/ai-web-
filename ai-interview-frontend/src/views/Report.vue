<template>
  <div class="container">
    <div v-if="loading" class="loading">加载报告中...</div>

    <div v-else-if="report" class="report-wrapper">
      <div class="card score-card">
        <div class="score-circle">
          <span class="score-num">{{ data.overall_score }}</span>
          <span class="score-label">/10</span>
        </div>
        <div class="score-info">
          <h2>岗位面试评估报告</h2>
          <p v-if="report.hire_recommendation" class="hire-rec">{{ report.hire_recommendation }}</p>
        </div>
      </div>

      <div v-if="report.summary" class="card section-card">
        <h3>总体评价</h3>
        <p class="section-text">{{ report.summary }}</p>
      </div>

      <div v-if="data.interview_mode === 'panel'" class="card panel-note-card section-card">
        <h3>多角色协同评估模式</h3>
        <p class="panel-note-text">
          本场测评启用了“内部多角色协同 + 单主持人对外输出”模式。你看到的提问与反馈，来自岗位画像、简历证据和表达逻辑等多个视角的综合判断。
        </p>
        <p v-if="report.mode_label" class="panel-mode-label">{{ report.mode_label }}</p>
      </div>

      <div v-if="report.matching_metrics" class="card section-card">
        <h3>岗位匹配指标</h3>
        <div class="metric-row">
          <span>关键词覆盖：{{ percentText(report.matching_metrics.keyword_coverage?.score) }}</span>
          <span>语义分：{{ report.matching_metrics.semantic_score ?? '-' }}</span>
          <span class="semantic-source">{{ semanticSourceLabel(report.matching_metrics) }}</span>
          <span>规则分：{{ report.matching_metrics.rule_score ?? '-' }}</span>
          <span>最终分：{{ report.matching_metrics.final_score ?? '-' }}</span>
        </div>
      </div>

      <div v-if="report.panel_summary?.length" class="card section-card">
        <h3>分视角结论</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.panel_summary" :key="i">{{ formatInsightItem(item) }}</li>
        </ul>
      </div>

      <div v-if="report.training_priorities?.length" class="card section-card">
        <h3>后续求职训练建议</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.training_priorities" :key="i">{{ formatInsightItem(item) }}</li>
        </ul>
      </div>

      <div v-if="report.common_gaps?.length" class="card section-card">
        <h3>高频短板</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.common_gaps" :key="i">{{ formatInsightItem(item) }}</li>
        </ul>
      </div>

      <div v-if="report.common_strengths?.length" class="card section-card">
        <h3>高频补强证据</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.common_strengths" :key="`strength-${i}`">{{ formatInsightItem(item) }}</li>
        </ul>
      </div>

      <div v-if="report.followup_loop_summary?.length" class="card section-card">
        <h3>追问闭环摘要</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.followup_loop_summary" :key="`loop-${i}`">{{ formatInsightItem(item) }}</li>
        </ul>
      </div>

      <div v-if="report.claim_confidence_summary?.length" class="card section-card">
        <h3>高风险表述变化</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.claim_confidence_summary" :key="`claim-${i}`">{{ formatInsightItem(item) }}</li>
        </ul>
      </div>

      <div v-if="report.evidence_summary?.length" class="card section-card">
        <h3>评估依据</h3>
        <ul class="panel-list">
          <li v-for="(item, i) in report.evidence_summary" :key="`evidence-${i}`">{{ formatInsightItem(item) }}</li>
        </ul>
        <p v-if="report.evidence_stats" class="panel-mode-label">
          已覆盖 {{ report.evidence_stats.questions_with_evidence || 0 }}/{{ report.evidence_stats.total_questions || data.total_questions || 0 }} 题，
          共命中 {{ report.evidence_stats.retrieved_slice_count || 0 }} 条关键切片。
        </p>
      </div>

      <div class="two-col section-card">
        <div v-if="report.strengths?.length" class="card">
          <h3 class="good-title">优势</h3>
          <ul class="basic-list">
            <li v-for="(s, i) in report.strengths" :key="i">{{ s }}</li>
          </ul>
        </div>
        <div v-if="report.weaknesses?.length" class="card">
          <h3 class="bad-title">不足</h3>
          <ul class="basic-list">
            <li v-for="(w, i) in report.weaknesses" :key="i">{{ w }}</li>
          </ul>
        </div>
      </div>

      <div v-if="report.suggestions?.length" class="card section-card">
        <h3>改进建议</h3>
        <ul class="basic-list">
          <li v-for="(s, i) in report.suggestions" :key="i">{{ s }}</li>
        </ul>
      </div>

      <div v-if="report.question_scores?.length" class="card section-card">
        <h3>各题得分</h3>
        <div v-for="(q, i) in report.question_scores" :key="i" class="q-score-item">
          <div class="q-score-header">
            <span class="q-index">Q{{ i + 1 }}</span>
            <span class="q-text">{{ q.question }}</span>
            <span
              class="q-score"
              :style="{ color: q.score >= 7 ? '#059669' : q.score >= 5 ? '#d97706' : '#dc2626' }"
            >
              {{ q.score }}
            </span>
          </div>
          <div class="q-bar">
            <div
              class="q-bar-fill"
              :style="{ width: `${q.score * 10}%`, background: q.score >= 7 ? '#10b981' : q.score >= 5 ? '#f59e0b' : '#ef4444' }"
            ></div>
          </div>
        </div>
      </div>

      <div class="report-actions">
        <router-link
          to="/resume/upload"
          class="btn-primary"
          style="display:inline-block;padding:10px 24px;color:white;border-radius:8px;margin-right:12px"
        >
          再测一次
        </router-link>
        <router-link
          to="/dashboard"
          class="btn-secondary"
          style="display:inline-block;padding:10px 24px;border-radius:8px"
        >
          返回工作台
        </router-link>
      </div>
    </div>

    <div v-else class="card empty-card">
      <p>报告加载失败</p>
      <router-link to="/dashboard" class="empty-link">返回工作台</router-link>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getReport } from '../api/interview'

const route = useRoute()
const interviewId = route.params.id
const data = ref(null)
const report = ref(null)
const loading = ref(true)

function formatInsightItem(item) {
  if (!item) return ''
  if (typeof item === 'string') return item
  if (typeof item === 'object') {
    if (item.title && item.summary) return `${item.title}：${item.summary}`
    return item.summary || item.title || item.focus || item.priority || JSON.stringify(item)
  }
  return String(item)
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

onMounted(async () => {
  try {
    const res = await getReport(interviewId)
    data.value = res
    report.value = res.report || {}
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.loading {
  text-align: center;
  padding: 80px;
  color: #6b7280;
}

.report-wrapper {
  max-width: 700px;
  margin: 30px auto;
}

.section-card {
  margin-top: 16px;
}

.score-card {
  display: flex;
  align-items: center;
  gap: 24px;
}

.score-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.score-num {
  font-size: 32px;
  font-weight: 700;
  color: white;
}

.score-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.score-info h2 {
  font-size: 20px;
  margin-bottom: 4px;
}

.hire-rec {
  font-size: 14px;
  color: #6b7280;
  margin-top: 4px;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.metric-row span {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f9fafb;
  color: #374151;
  font-size: 13px;
}

.metric-row .semantic-source {
  background: #eef2ff;
  color: #4338ca;
}

.section-text {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
}

.panel-note-card {
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(16, 185, 129, 0.08));
  border: 1px solid rgba(79, 70, 229, 0.12);
}

.panel-note-text {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
}

.panel-mode-label {
  margin-top: 10px;
  font-size: 12px;
  color: #4338ca;
}

.panel-list,
.basic-list {
  list-style: none;
  padding: 0;
}

.panel-list li,
.basic-list li {
  position: relative;
  padding-left: 16px;
  font-size: 14px;
  line-height: 1.8;
}

.panel-list li::before,
.basic-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #6b7280;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.good-title {
  margin-bottom: 10px;
  color: #059669;
}

.bad-title {
  margin-bottom: 10px;
  color: #dc2626;
}

.q-score-item {
  margin-bottom: 14px;
}

.q-score-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 14px;
}

.q-index {
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 12px;
  color: #6b7280;
}

.q-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.q-score {
  font-weight: 700;
  font-size: 16px;
}

.q-bar {
  height: 6px;
  background: #f3f4f6;
  border-radius: 3px;
  overflow: hidden;
}

.q-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.report-actions {
  text-align: center;
  margin-top: 24px;
  margin-bottom: 40px;
}

.empty-card {
  text-align: center;
  padding: 60px;
  max-width: 500px;
  margin: 60px auto;
}

.empty-link {
  margin-top: 12px;
  display: inline-block;
}

@media (max-width: 768px) {
  .score-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .two-col {
    grid-template-columns: 1fr;
  }

  .metric-row {
    grid-template-columns: 1fr 1fr;
  }

  .q-score-header {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .q-text {
    white-space: normal;
  }
}
</style>
