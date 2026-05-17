<template>
  <div>
    <div class="page-head">
      <div>
        <h1 style="font-size:20px;margin-bottom:6px">评测样本与人工评分对比</h1>
        <p class="helper-text">
          基于已完成、已获得本次案例去标识化数据贡献授权且已人工标注的测评样本，预览模型验证数据、微调准备样本，并按固定规则导出 ZIP + JSONL。
        </p>
      </div>
      <div class="head-actions">
        <button class="btn-primary" :disabled="exportLoading || !hasCompletedSamples" @click="downloadBundle">
          {{ exportLoading ? '导出中...' : '导出验证数据 ZIP' }}
        </button>
        <button class="btn-secondary" :disabled="fineTuningExportLoading || !hasFineTuningSamples" @click="downloadFineTuningJsonl">
          {{ fineTuningExportLoading ? '导出中...' : '导出微调 JSONL' }}
        </button>
        <button class="btn-secondary" :disabled="reportExportLoading" @click="downloadFineTuningReport">
          {{ reportExportLoading ? '导出中...' : '导出准备报告 MD' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="card state-card">加载评测样本预览中...</div>
    <div v-else-if="errorMessage" class="card state-card error-text">{{ errorMessage }}</div>

    <template v-else-if="preview">
      <div v-if="preview.diagnostic?.warning" class="card warning-card">
        {{ preview.diagnostic.warning }}
      </div>

      <div class="stats-grid" style="margin-bottom:16px">
        <div class="card stat-card">
          <div class="stat-label">Schema</div>
          <div class="stat-value">{{ preview.schema_version }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">已授权完成测评</div>
          <div class="stat-value">{{ preview.stats?.completed_samples || 0 }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">人工复核样本</div>
          <div class="stat-value">{{ preview.stats?.reviewed_samples || 0 }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">验证集归档次数</div>
          <div class="stat-value">{{ preview.stats?.dataset_assignments || 0 }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">微调准备样本</div>
          <div class="stat-value">{{ fineTuningStats.sft_ready_samples || 0 }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">幻觉反例</div>
          <div class="stat-value">{{ fineTuningStats.hallucination_counterexamples || 0 }}</div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <h3 style="margin-bottom:10px">固定规则</h3>
        <div class="rule-summary">
          <div>
            <div class="info-label">公共前置条件</div>
            <ul class="simple-list">
              <li v-for="item in preview.filters?.base_requirements || []" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <div class="info-label">固定阈值</div>
            <ul class="simple-list">
              <li v-for="(value, key) in preview.filters?.thresholds || {}" :key="key">{{ key }} = {{ value }}</li>
            </ul>
          </div>
          <div>
            <div class="info-label">导出策略</div>
            <ul class="simple-list">
              <li>集合允许重叠：{{ preview.filters?.overlap_allowed ? '是' : '否' }}</li>
              <li>默认包含 PII：{{ preview.filters?.pii_included ? '是' : '否' }}</li>
              <li>导出时间：{{ formatTime(preview.generated_at) }}</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div class="dataset-head" style="margin-bottom:12px">
          <div>
            <h3 style="margin-bottom:6px">大模型微调准备层</h3>
            <p class="helper-text">
              这里不宣称已完成底层模型训练，而是把授权、人工复核后的样本整理为后续 SFT/LoRA 可使用的 JSONL 结构，并可导出答辩用微调准备报告。
            </p>
          </div>
          <span class="fine-tuning-badge">schema {{ preview.fine_tuning?.schema_version || '-' }}</span>
        </div>
        <div class="rule-summary">
          <div>
            <div class="info-label">样本统计</div>
            <ul class="simple-list">
              <li>已授权样本：{{ fineTuningStats.authorized_samples || 0 }}</li>
              <li>已人工复核：{{ fineTuningStats.reviewed_samples || 0 }}</li>
              <li>高质量候选：{{ fineTuningStats.high_quality_samples || 0 }}</li>
              <li>SFT 可用样本：{{ fineTuningStats.sft_ready_samples || 0 }}</li>
            </ul>
          </div>
          <div>
            <div class="info-label">准入规则</div>
            <ul class="simple-list">
              <li v-for="item in preview.fine_tuning?.base_requirements || []" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <div class="info-label">JSONL 字段</div>
            <div class="field-chips">
              <span v-for="item in preview.fine_tuning?.jsonl_fields || []" :key="item" class="id-chip">{{ item }}</span>
            </div>
          </div>
        </div>
        <div class="fine-file-grid">
          <div v-for="file in preview.fine_tuning?.files || []" :key="file.filename" class="fine-file">
            <strong>{{ file.label }}</strong>
            <span>{{ file.filename }}</span>
            <em>{{ file.count }} 条</em>
            <p>{{ file.description }}</p>
          </div>
        </div>
        <p class="report-tip">
          准备报告会汇总数据来源、准入规则、去标识化策略、样本分层、可训练任务和风险边界，适合放入答辩资料包。
        </p>
      </div>

      <div class="card competition-preview-card" style="margin-bottom:16px">
        <div class="dataset-head" style="margin-bottom:12px">
          <div>
            <h3 style="margin-bottom:6px">比赛 Preview 展示层</h3>
            <p class="helper-text">
              这里展示 Career-AgentOS 沙盘样本和 SFT Preview。它只用于答辩演示与链路验证，不混入真实训练样本导出，也不代表已完成 OpenAI SFT。
            </p>
            <p v-if="competitionErrorMessage" class="error-text" style="margin-top:8px">
              比赛 Preview 加载失败：{{ competitionErrorMessage }}
            </p>
          </div>
          <span class="fine-tuning-badge">preview only</span>
        </div>
        <div class="rule-summary">
          <div>
            <div class="info-label">三岗位沙盘</div>
            <ul class="simple-list">
              <li v-for="item in competitionCases" :key="item.case_id">
                {{ item.target_role }}：{{ item.sample_origin }} / for_training=false
              </li>
              <li v-if="!competitionCases.length">暂无本地 demo_cases，后端将使用内置演示兜底。</li>
            </ul>
          </div>
          <div>
            <div class="info-label">SFT Preview</div>
            <ul class="simple-list">
              <li>演示样本：{{ competitionSftSummary.counts?.demo_constructed || 0 }}</li>
              <li>真实授权样本：{{ competitionSftSummary.counts?.real_authorized || 0 }}</li>
              <li>训练预览记录：{{ competitionSftSummary.counts?.train_preview_records || 0 }}</li>
              <li>可真实训练：{{ competitionSftSummary.ready_for_real_training ? '是' : '否' }}</li>
            </ul>
          </div>
          <div>
            <div class="info-label">任务类型</div>
            <div class="field-chips">
              <span v-for="item in competitionSftSummary.tasks || []" :key="item" class="id-chip">{{ item }}</span>
              <span v-if="!(competitionSftSummary.tasks || []).length" class="id-chip">preview/demo</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!hasCompletedSamples" class="card state-card" style="margin-bottom:16px">
        <p style="font-weight:600;margin-bottom:8px">暂无可导出的测评样本</p>
        <p class="helper-text">
          需要先完成模拟面试，在报告页或训练复盘页取得本次案例数据贡献授权，再到“案例标注工作台”完成人工标注，评测样本才会进入验证数据预览。
        </p>
      </div>

      <div class="dataset-grid">
        <div v-for="dataset in preview.datasets || []" :key="dataset.dataset_type" class="card dataset-card">
          <div class="dataset-head">
            <div>
              <h3 style="margin-bottom:4px">{{ dataset.label }}</h3>
              <div class="dataset-file">{{ dataset.filename }}</div>
            </div>
            <div class="dataset-count">{{ dataset.count }}</div>
          </div>
          <p class="helper-text" style="margin-bottom:12px">{{ dataset.description }}</p>

          <div style="margin-bottom:12px">
            <div class="info-label">示例测评 ID</div>
            <div v-if="dataset.example_interview_ids?.length" class="example-ids">
              <span v-for="item in dataset.example_interview_ids" :key="item" class="id-chip">#{{ item }}</span>
            </div>
            <div v-else class="helper-text">暂无命中样本</div>
          </div>

          <div>
            <div class="info-label">命中规则</div>
            <ul class="simple-list">
              <li v-for="rule in dataset.rules || []" :key="rule">{{ rule }}</li>
            </ul>
          </div>
        </div>
      </div>

      <p v-if="noticeMessage" :class="['notice-text', noticeType === 'error' ? 'error-text' : 'success-text']">
        {{ noticeMessage }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { competitionApi, interviewApi } from '../api'

const loading = ref(true)
const exportLoading = ref(false)
const fineTuningExportLoading = ref(false)
const reportExportLoading = ref(false)
const preview = ref(null)
const competitionCases = ref([])
const competitionSftPreview = ref({})
const competitionErrorMessage = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')
const noticeType = ref('success')

const hasCompletedSamples = computed(() => Number(preview.value?.stats?.completed_samples || 0) > 0)
const fineTuningStats = computed(() => preview.value?.fine_tuning?.stats || {})
const hasFineTuningSamples = computed(() => Number(fineTuningStats.value.sft_ready_samples || 0) > 0)
const competitionSftSummary = computed(() => competitionSftPreview.value?.summary || {})

const formatTime = (value) => {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

const loadPreview = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    preview.value = await interviewApi.evaluationDatasetPreview()
  } catch (error) {
    errorMessage.value = error.message || '加载评测集预览失败；请先确认后端服务和数据库迁移状态'
  } finally {
    loading.value = false
  }
}

const downloadBundle = async () => {
  exportLoading.value = true
  noticeMessage.value = ''
  try {
    const response = await interviewApi.exportEvaluationDatasets()
    const blob = response.data
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'zhiqi-evaluation-datasets.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    noticeType.value = 'success'
    noticeMessage.value = '验证数据 ZIP 已导出'
  } catch (error) {
    noticeType.value = 'error'
    noticeMessage.value = error.message || '导出评测集失败'
  } finally {
    exportLoading.value = false
  }
}

const loadCompetitionPreview = async () => {
  competitionErrorMessage.value = ''
  try {
    const caseResult = await competitionApi.demoCases()
    competitionCases.value = caseResult.items || []
    competitionSftPreview.value = await competitionApi.sftPreview()
  } catch (error) {
    competitionCases.value = []
    competitionSftPreview.value = {}
    competitionErrorMessage.value = error.message || '后端 Competition Preview 接口不可用'
  }
}

const downloadFineTuningJsonl = async () => {
  fineTuningExportLoading.value = true
  noticeMessage.value = ''
  try {
    const response = await interviewApi.exportFineTuningSamples()
    const blob = response.data
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'zhiqi-fine-tuning-sft.jsonl'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    noticeType.value = 'success'
    noticeMessage.value = '微调准备 JSONL 已导出'
  } catch (error) {
    noticeType.value = 'error'
    noticeMessage.value = error.message || '导出微调 JSONL 失败'
  } finally {
    fineTuningExportLoading.value = false
  }
}

const downloadFineTuningReport = async () => {
  reportExportLoading.value = true
  noticeMessage.value = ''
  try {
    const response = await interviewApi.exportFineTuningReport()
    const blob = response.data
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'zhiqi-fine-tuning-readiness-report.md'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    noticeType.value = 'success'
    noticeMessage.value = '微调准备报告 MD 已导出'
  } catch (error) {
    noticeType.value = 'error'
    noticeMessage.value = error.message || '导出微调准备报告失败'
  } finally {
    reportExportLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadPreview(), loadCompetitionPreview()])
})
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.head-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.helper-text {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-label,
.info-label {
  font-size: 12px;
  color: #6b7280;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}
.rule-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.dataset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.dataset-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dataset-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.dataset-file {
  font-size: 12px;
  color: #111827;
  font-family: monospace;
}
.dataset-count {
  min-width: 44px;
  height: 44px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #111827;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.simple-list {
  margin: 6px 0 0;
  padding-left: 18px;
  color: #374151;
  font-size: 13px;
  line-height: 1.7;
}
.example-ids {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.field-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.id-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 12px;
}
.fine-tuning-badge {
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
  padding: 7px 10px;
  white-space: nowrap;
}
.fine-file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.fine-file {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.fine-file span {
  font-family: monospace;
  font-size: 12px;
  color: #111827;
}
.fine-file em {
  font-style: normal;
  font-size: 13px;
  color: #047857;
}
.fine-file p {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}
.report-tip {
  margin-top: 12px;
  border-left: 3px solid #4f46e5;
  padding: 8px 10px;
  background: #f8fafc;
  color: #374151;
  font-size: 13px;
  line-height: 1.7;
}
.competition-preview-card {
  border-left: 4px solid #0f766e;
}
.btn-primary,
.btn-secondary {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 14px;
  cursor: pointer;
}
.btn-primary {
  background: #111827;
  color: white;
}
.btn-secondary {
  background: #f3f4f6;
  color: #111827;
}
.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.notice-text {
  margin-top: 16px;
  font-size: 13px;
}
.success-text { color: #059669; }
.error-text { color: #dc2626; }
.state-card {
  padding: 32px;
  text-align: center;
}
.warning-card {
  margin-bottom: 16px;
  border-color: #fde68a;
  background: #fffbeb;
  color: #92400e;
  line-height: 1.7;
}
</style>
