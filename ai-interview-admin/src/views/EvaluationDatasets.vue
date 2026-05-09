<template>
  <div>
    <div class="page-head">
      <div>
        <h1 style="font-size:20px;margin-bottom:6px">评测样本与人工评分对比</h1>
        <p class="helper-text">
          基于已完成且已人工标注的测评样本，预览答辩验证数据，并按固定规则导出 ZIP + JSONL。
        </p>
      </div>
      <button class="btn-primary" :disabled="exportLoading || !hasCompletedSamples" @click="downloadBundle">
        {{ exportLoading ? '导出中...' : '导出验证数据 ZIP' }}
      </button>
    </div>

    <div v-if="loading" class="card state-card">加载评测样本预览中...</div>
    <div v-else-if="errorMessage" class="card state-card error-text">{{ errorMessage }}</div>

    <template v-else-if="preview">
      <div class="stats-grid" style="margin-bottom:16px">
        <div class="card stat-card">
          <div class="stat-label">Schema</div>
          <div class="stat-value">{{ preview.schema_version }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">已完成测评</div>
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

      <div v-if="!hasCompletedSamples" class="card state-card" style="margin-bottom:16px">
        <p style="font-weight:600;margin-bottom:8px">暂无可导出的测评样本</p>
        <p class="helper-text">
          需要先在用户端完成至少一场模拟面试，再到“面试记录”详情中做人工标注，评测样本才会进入验证数据预览。
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

import { interviewApi } from '../api'

const loading = ref(true)
const exportLoading = ref(false)
const preview = ref(null)
const errorMessage = ref('')
const noticeMessage = ref('')
const noticeType = ref('success')

const hasCompletedSamples = computed(() => Number(preview.value?.stats?.completed_samples || 0) > 0)

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

onMounted(loadPreview)
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
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
  color: #6366f1;
  font-family: monospace;
}
.dataset-count {
  min-width: 44px;
  height: 44px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
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
.id-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 12px;
}
.btn-primary {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 14px;
  background: #4f46e5;
  color: white;
  cursor: pointer;
}
.btn-primary:disabled {
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
</style>
