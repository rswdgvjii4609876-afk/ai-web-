<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <router-link to="/interviews" style="color:#6b7280;font-size:14px">← 返回列表</router-link>
      <h1 style="font-size:20px">面试详情 #{{ interviewId }}</h1>
    </div>

    <div v-if="loading" style="text-align:center;padding:60px;color:#6b7280">加载中...</div>

    <template v-else-if="detail">
      <div class="card" style="margin-bottom:16px">
        <div class="info-grid">
          <div><span class="info-label">目标岗位</span><span>{{ detail.target_position || '-' }}</span></div>
          <div><span class="info-label">难度</span><span>{{ diffMap[detail.difficulty] || detail.difficulty || '-' }}</span></div>
          <div><span class="info-label">题数</span><span>{{ detail.total_questions }}</span></div>
          <div><span class="info-label">综合得分</span><span style="font-weight:700;color:#4f46e5">{{ detail.overall_score || '-' }}</span></div>
          <div><span class="info-label">状态</span><span :class="['badge', detail.status === 'completed' ? 'badge-green' : 'badge-yellow']">{{ detail.status === 'completed' ? '已完成' : '进行中' }}</span></div>
          <div><span class="info-label">模式</span><span>{{ interviewModeMap[detail.interview_mode] || detail.interview_mode || '-' }}</span></div>
          <div><span class="info-label">人工标注</span><span :class="['badge', reviewStatusClass]">{{ reviewStatusText }}</span></div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px">
          <div>
            <h3 style="margin-bottom:6px">评测样本人工标注</h3>
            <p class="helper-text">
              这一步服务于答辩验证和人工评分对比。后台可判断一场测评是否适合作为高质量样本、是否存在无依据判断、追问是否有训练价值，再决定是否导出。
            </p>
          </div>
          <div class="export-hint" :class="exportRecommended ? 'export-good' : 'export-warn'">
            {{ exportRecommended ? '建议进入导出池' : '建议继续复核后再导出' }}
          </div>
        </div>

        <div class="review-grid">
          <label class="review-field">
            <span>质量等级</span>
            <select v-model="reviewForm.quality_tier">
              <option v-for="option in qualityOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <label class="review-check">
            <input v-model="reviewForm.is_high_quality" type="checkbox">
            <span>高质量样本</span>
          </label>
          <label class="review-check">
            <input v-model="reviewForm.has_hallucination" type="checkbox">
            <span>存在幻觉/无依据强答</span>
          </label>
          <label class="review-check">
            <input v-model="reviewForm.followup_worthy" type="checkbox">
            <span>追问有训练价值</span>
          </label>
          <label class="review-check">
            <input v-model="reviewForm.report_actionable" type="checkbox">
            <span>报告建议可执行</span>
          </label>
        </div>

        <label class="review-field" style="margin-top:14px">
          <span>复核备注</span>
          <textarea
            v-model="reviewForm.notes"
            rows="5"
            placeholder="记录为什么判为高质量、哪里出现幻觉、哪些追问值得进入黄金样本。"
          />
        </label>

        <div class="review-meta" v-if="detail.training_sample_review?.reviewed_at">
          最近标注：{{ detail.training_sample_review.reviewer_email || '未知管理员' }} · {{ formatReviewTime(detail.training_sample_review.reviewed_at) }}
        </div>

        <div class="review-actions">
          <button class="btn-primary" :disabled="saveLoading" @click="saveReview">
            {{ saveLoading ? '保存中...' : '保存标注' }}
          </button>
          <button
            class="btn-secondary"
            :disabled="exportLoading || detail.status !== 'completed'"
            @click="downloadTrainingSample"
          >
            {{ exportLoading ? '导出中...' : '导出评测样本 JSON' }}
          </button>
          <span class="helper-text" v-if="detail.status !== 'completed'">仅已完成测评可导出评测样本</span>
        </div>

        <p v-if="reviewNotice" :class="['review-notice', reviewNoticeType === 'error' ? 'notice-error' : 'notice-success']">
          {{ reviewNotice }}
        </p>
      </div>

      <div class="card" style="margin-bottom:16px" v-if="hasReportContent">
        <h3 style="margin-bottom:12px">求职能力评估报告</h3>
        <p v-if="detail.report?.summary" style="font-size:14px;line-height:1.8;margin-bottom:12px">{{ detail.report.summary }}</p>
        <div class="report-cols" v-if="detail.report?.strengths?.length || detail.report?.weaknesses?.length">
          <div v-if="detail.report?.strengths?.length">
            <h4 style="color:#059669;margin-bottom:6px">优势</h4>
            <ul><li v-for="s in detail.report.strengths" :key="s">{{ s }}</li></ul>
          </div>
          <div v-if="detail.report?.weaknesses?.length">
            <h4 style="color:#dc2626;margin-bottom:6px">不足</h4>
            <ul><li v-for="w in detail.report.weaknesses" :key="w">{{ w }}</li></ul>
          </div>
        </div>
      </div>

      <div class="card">
        <h3 style="margin-bottom:16px">💬 对话记录</h3>
        <div v-for="m in detail.messages" :key="m.id" :class="['msg', m.role]">
          <div class="msg-role">{{ m.role === 'interviewer' ? '职启智评面试官' : '候选人' }}</div>
          <div class="msg-content">{{ m.content }}</div>
          <div v-if="m.score" class="msg-score">
            评分: {{ m.score }}/10
            <span v-if="m.feedback"> | {{ m.feedback }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { interviewApi } from '../api'

const route = useRoute()
const interviewId = route.params.id
const detail = ref(null)
const loading = ref(true)
const saveLoading = ref(false)
const exportLoading = ref(false)
const reviewNotice = ref('')
const reviewNoticeType = ref('success')

const diffMap = { easy: '简单', medium: '中等', hard: '困难' }
const interviewModeMap = { single: '单面试官', panel: '多角色内评' }
const qualityOptions = [
  { value: 'needs_review', label: '待复核' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' }
]

const createDefaultReview = () => ({
  quality_tier: 'needs_review',
  is_high_quality: false,
  has_hallucination: false,
  followup_worthy: false,
  report_actionable: false,
  notes: ''
})

const reviewForm = ref(createDefaultReview())

const applyReviewToForm = (review = null) => {
  reviewForm.value = {
    ...createDefaultReview(),
    ...(review || {}),
    notes: review?.notes || ''
  }
}

const reviewStatusText = computed(() => {
  const status = detail.value?.training_sample_review?.review_status
  return status === 'reviewed' ? '已标注' : '待标注'
})

const reviewStatusClass = computed(() => (
  detail.value?.training_sample_review?.review_status === 'reviewed' ? 'badge-green' : 'badge-yellow'
))

const exportRecommended = computed(() => (
  !!reviewForm.value.is_high_quality && !reviewForm.value.has_hallucination
))

const hasReportContent = computed(() => (
  !!detail.value?.report?.summary ||
  !!detail.value?.report?.strengths?.length ||
  !!detail.value?.report?.weaknesses?.length
))

const formatReviewTime = (value) => {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

const loadDetail = async () => {
  loading.value = true
  try {
    detail.value = await interviewApi.detail(interviewId)
    applyReviewToForm(detail.value.training_sample_review)
  } catch (error) {
    reviewNoticeType.value = 'error'
    reviewNotice.value = error.message || '加载测评详情失败'
  } finally {
    loading.value = false
  }
}

const saveReview = async () => {
  saveLoading.value = true
  reviewNotice.value = ''
  try {
    const saved = await interviewApi.updateTrainingReview(interviewId, reviewForm.value)
    detail.value.training_sample_review = saved
    applyReviewToForm(saved)
    reviewNoticeType.value = 'success'
    reviewNotice.value = '评测样本标注已保存'
  } catch (error) {
    reviewNoticeType.value = 'error'
    reviewNotice.value = error.message || '保存标注失败'
  } finally {
    saveLoading.value = false
  }
}

const downloadTrainingSample = async () => {
  exportLoading.value = true
  reviewNotice.value = ''
  try {
    const sample = await interviewApi.trainingSample(interviewId)
    const blob = new Blob([JSON.stringify(sample, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `evaluation-sample-${interviewId}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    reviewNoticeType.value = 'success'
    reviewNotice.value = '评测样本已导出'
  } catch (error) {
    reviewNoticeType.value = 'error'
    reviewNotice.value = error.message || '导出评测样本失败'
  } finally {
    exportLoading.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.info-grid { display: flex; gap: 24px; flex-wrap: wrap; }
.info-grid > div { display: flex; flex-direction: column; gap: 4px; min-width: 110px; }
.info-label { font-size: 12px; color: #6b7280; }
.helper-text { font-size: 13px; color: #6b7280; line-height: 1.7; }
.report-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.report-cols ul { list-style: none; padding: 0; }
.report-cols li { font-size: 13px; line-height: 1.8; padding-left: 14px; position: relative; }
.report-cols li::before { content: '•'; position: absolute; left: 0; color: #9ca3af; }
.review-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: start; }
.review-field { display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #374151; }
.review-field select,
.review-field textarea {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  background: #fff;
}
.review-field textarea { resize: vertical; min-height: 96px; }
.review-check {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  background: #f9fafb;
  font-size: 13px;
  color: #374151;
}
.review-meta { margin-top: 12px; font-size: 12px; color: #6b7280; }
.review-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 16px; }
.btn-primary,
.btn-secondary {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 14px;
  cursor: pointer;
}
.btn-primary {
  background: #4f46e5;
  color: white;
}
.btn-secondary {
  background: #eef2ff;
  color: #4338ca;
}
.btn-primary:disabled,
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.review-notice { margin-top: 14px; font-size: 13px; }
.notice-success { color: #059669; }
.notice-error { color: #dc2626; }
.export-hint {
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  white-space: nowrap;
}
.export-good {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}
.export-warn {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}
.msg { margin-bottom: 16px; padding: 12px; border-radius: 8px; }
.msg.interviewer { background: #f9fafb; }
.msg.candidate { background: #eef2ff; }
.msg-role { font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 6px; }
.msg-content { font-size: 14px; line-height: 1.7; }
.msg-score { margin-top: 8px; font-size: 12px; color: #4f46e5; font-weight: 500; }
</style>
