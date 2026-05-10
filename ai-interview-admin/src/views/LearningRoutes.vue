<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>学习路线管理</h1>
        <p>维护能力差距生成学习任务时使用的路线阶段。系统优先使用启用的后台路线，没有匹配时再回退内置路线。</p>
      </div>
      <div class="head-actions">
        <button class="btn-secondary" type="button" @click="exportRoutes">导出 JSON</button>
        <button class="btn-secondary" type="button" @click="triggerImport">导入 JSON</button>
        <input ref="importInput" class="hidden-input" type="file" accept="application/json,.json" @change="handleImport" />
        <button class="btn-primary" type="button" @click="startCreate">
          {{ editingId ? '新建路线阶段' : '+ 新建路线阶段' }}
        </button>
      </div>
    </header>

    <section class="stats-grid">
      <div class="stat-card"><span>路线阶段</span><strong>{{ stats.total }}</strong></div>
      <div class="stat-card"><span>启用中</span><strong>{{ stats.active_total }}</strong></div>
      <div class="stat-card"><span>完整路线</span><strong>{{ qualitySummary.complete_total }}</strong></div>
      <div class="stat-card"><span>需补充</span><strong>{{ qualitySummary.needs_improvement_total }}</strong></div>
      <div class="stat-card"><span>不建议启用</span><strong>{{ qualitySummary.not_recommended_total }}</strong></div>
      <div class="stat-card"><span>缺练习任务</span><strong>{{ qualitySummary.missing_practice_total }}</strong></div>
      <div class="stat-card"><span>缺验收方式</span><strong>{{ qualitySummary.missing_acceptance_total }}</strong></div>
      <div class="stat-card"><span>缺关键词</span><strong>{{ qualitySummary.missing_keywords_total }}</strong></div>
    </section>

    <section class="panel coverage-panel">
      <div class="section-head">
        <div>
          <h2>岗位路线覆盖矩阵</h2>
          <p>按岗位画像能力项检查启用路线覆盖情况，帮助定位哪些能力还需要补路线。</p>
        </div>
        <button class="btn-secondary" type="button" @click="loadCoverage">刷新覆盖</button>
      </div>

      <div class="coverage-summary">
        <span>岗位 {{ coverageSummary.total_positions || 0 }}</span>
        <span>覆盖良好 {{ coverageSummary.good_total || 0 }}</span>
        <span>需补路线 {{ coverageSummary.needs_route_total || 0 }}</span>
        <span>不建议上线 {{ coverageSummary.not_recommended_total || 0 }}</span>
        <span>平均覆盖率 {{ coverageSummary.average_coverage_rate || 0 }}%</span>
      </div>

      <div v-if="coverageLoading" class="coverage-empty">正在计算覆盖矩阵...</div>
      <div v-else class="coverage-grid">
        <button
          v-for="row in coverageItems"
          :key="row.job_id"
          type="button"
          :class="['coverage-card', row.status, selectedCoverageJob === row.job_id ? 'selected' : '']"
          @click="selectedCoverageJob = row.job_id"
        >
          <strong>{{ row.job_name }}</strong>
          <span>{{ row.status_label }} · {{ row.coverage_rate }}%</span>
          <small>{{ row.matched_ability_total }}/{{ row.ability_total }} 能力已匹配 · 启用路线 {{ row.active_route_total }}</small>
        </button>
      </div>

      <div v-if="selectedCoverage" class="ability-match-panel">
        <h3>{{ selectedCoverage.job_name }}能力匹配预览</h3>
        <div class="ability-match-list">
          <div v-for="ability in selectedCoverage.ability_matches" :key="ability.ability_id" class="ability-match-item">
            <div>
              <strong>{{ ability.ability_name }}</strong>
              <p>{{ ability.matched ? `${ability.stage_title} / ${ability.route_stage}` : '待补路线' }}</p>
            </div>
            <span :class="['match-pill', ability.matched ? ability.quality_level || 'complete' : 'missing']">
              {{ ability.matched ? ability.quality_label : '待补路线' }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <section class="route-layout">
      <div class="left-column">
        <form class="panel route-form" @submit.prevent="handleSubmit">
          <h2>{{ editingId ? '编辑路线阶段' : '新增路线阶段' }}</h2>
          <div class="form-grid two">
            <label>岗位 ID<input v-model="form.job_id" placeholder="例如 python_backend，可为空表示按类别兜底" /></label>
            <label>岗位名称<input v-model="form.job_name" placeholder="例如 Python后端开发工程师" /></label>
            <label>岗位类别<input v-model="form.category" placeholder="例如 技术岗 / 产品岗 / 职能岗" /></label>
            <label>排序<input v-model.number="form.sort_order" type="number" /></label>
          </div>

          <div class="form-grid two">
            <label>路线来源<input v-model="form.route_source" placeholder="例如 backoffice_python_route" /></label>
            <label>阶段编码<input v-model="form.route_stage" placeholder="例如 fastapi_framework" /></label>
            <label>阶段名称<input v-model="form.stage_title" placeholder="例如 FastAPI 接口与工程结构" /></label>
            <label>材料类型<input v-model="form.material_type" placeholder="例如 python_backend_route" /></label>
            <label>
              任务类型
              <select v-model="form.task_type">
                <option v-for="type in taskTypeOptions" :key="type.value" :value="type.value">{{ type.label }}</option>
              </select>
            </label>
            <label>预计耗时（分钟）<input v-model.number="form.estimated_minutes" type="number" min="1" /></label>
          </div>

          <label>关键词<input v-model="keywordText" placeholder="用逗号分隔，例如 FastAPI,接口,异步" /></label>
          <label>学习材料<textarea v-model="form.learning_material" rows="4" placeholder="写清学习材料、资料来源或学习说明"></textarea></label>
          <label>练习任务<textarea v-model="form.practice_task" rows="4" placeholder="写成可执行任务，例如完成一个接口练习并记录异常处理"></textarea></label>
          <label>验收方式<textarea v-model="criteriaText" rows="4" placeholder="每行一条，例如：能独立说明接口设计取舍"></textarea></label>

          <label class="switch-row">
            <input v-model="form.is_active" type="checkbox" />
            <span>启用这一路线阶段</span>
          </label>

          <p v-if="message" :class="messageType === 'error' ? 'message error' : 'message success'">{{ message }}</p>

          <div class="form-actions">
            <button class="btn-primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '保存路线阶段' }}</button>
            <button v-if="editingId" class="btn-secondary" type="button" @click="resetForm">取消编辑</button>
          </div>
        </form>

        <section class="panel preview-panel">
          <h2>任务生成预览</h2>
          <div class="form-grid two">
            <label>路线 ID<input v-model.number="previewForm.route_id" type="number" placeholder="可从列表点预览自动填入" /></label>
            <label>目标岗位<input v-model="previewForm.target_position" placeholder="例如 Python后端开发工程师" /></label>
            <label>岗位 ID<input v-model="previewForm.job_id" placeholder="例如 python_backend" /></label>
            <label>岗位类别<input v-model="previewForm.category" placeholder="例如 技术岗" /></label>
          </div>
          <label>能力项<input v-model="previewForm.ability_name" placeholder="例如 接口设计能力" /></label>
          <label>缺口关键词<input v-model="previewKeywordsText" placeholder="用逗号分隔，例如 FastAPI,Redis,Docker" /></label>
          <label class="switch-row">
            <input v-model="previewForm.include_inactive" type="checkbox" />
            <span>允许预览停用路线</span>
          </label>
          <button class="btn-primary" type="button" :disabled="previewing" @click="handlePreview">
            {{ previewing ? '预览中...' : '生成任务预览' }}
          </button>

          <div v-if="previewResult" class="preview-result">
            <h3>{{ previewResult.task.title }}</h3>
            <p><strong>路线：</strong>{{ previewResult.route.stage_title || previewResult.route.title || previewResult.task.task_metadata?.route_stage_title }}</p>
            <p><strong>练习任务：</strong>{{ previewResult.task.practice_task }}</p>
            <p><strong>验收方式：</strong>{{ (previewResult.task.acceptance_criteria || []).join('；') }}</p>
            <p><strong>预计耗时：</strong>{{ previewResult.task.estimated_minutes || '-' }} 分钟</p>
          </div>
        </section>
      </div>

      <div class="route-main">
        <section class="panel filter-panel">
          <label>
            岗位
            <select v-model="filters.job_id" @change="loadRoutes">
              <option value="">全部岗位</option>
              <option v-for="job in filterOptions.job_ids" :key="job" :value="job">{{ job }}</option>
            </select>
          </label>
          <label>
            类别
            <select v-model="filters.category" @change="loadRoutes">
              <option value="">全部类别</option>
              <option v-for="category in filterOptions.categories" :key="category" :value="category">{{ category }}</option>
            </select>
          </label>
          <label>
            任务类型
            <select v-model="filters.task_type" @change="loadRoutes">
              <option value="">全部类型</option>
              <option v-for="type in filterOptions.task_types" :key="type" :value="type">{{ taskTypeLabel(type) }}</option>
            </select>
          </label>
          <label>
            状态
            <select v-model="filters.is_active" @change="loadRoutes">
              <option value="">全部状态</option>
              <option value="true">启用</option>
              <option value="false">停用</option>
            </select>
          </label>
          <label class="keyword-filter">搜索<input v-model="filters.keyword" placeholder="阶段名称 / 材料关键词" @keyup.enter="loadRoutes" /></label>
          <button class="btn-secondary" type="button" @click="loadRoutes">筛选</button>
        </section>

        <section v-if="loading" class="panel empty">正在加载学习路线...</section>
        <section v-else-if="!items.length" class="panel empty">还没有学习路线阶段。</section>
        <section v-else class="route-list">
          <article v-for="item in items" :key="item.route_id" class="panel route-item">
            <div class="route-head">
              <div>
                <h3>{{ item.stage_title }}</h3>
                <p>{{ item.job_name || item.job_id || item.category || '通用路线' }} · {{ item.route_stage }}</p>
              </div>
              <div class="pill-stack">
                <span :class="['status-pill', item.is_active ? 'on' : 'off']">{{ item.is_active ? '启用' : '停用' }}</span>
                <span :class="['quality-level', item.quality_level || 'needs_improvement']">{{ item.quality_label || qualityLabel(item) }}</span>
              </div>
            </div>

            <div class="route-meta">
              <span>{{ item.route_source }}</span>
              <span>{{ taskTypeLabel(item.task_type) }}</span>
              <span>{{ item.estimated_minutes || '-' }} 分钟</span>
              <span>排序 {{ item.sort_order }}</span>
            </div>

            <p class="route-material">{{ item.learning_material || '未填写学习材料' }}</p>

            <div class="tag-row">
              <span v-for="keyword in (item.keywords || []).slice(0, 8)" :key="`${item.route_id}-${keyword}`" class="tag">{{ keyword }}</span>
            </div>

            <div class="quality-row">
              <span v-if="!item.quality_hints.length" class="quality ok">质量检查通过</span>
              <span v-for="hint in item.quality_hints" :key="`${item.route_id}-${hint}`" class="quality warn">{{ hint }}</span>
            </div>

            <details class="route-detail">
              <summary>查看练习与验收</summary>
              <div>
                <strong>练习任务</strong>
                <p>{{ item.practice_task || '未填写' }}</p>
              </div>
              <div>
                <strong>验收方式</strong>
                <ul>
                  <li v-for="criterion in item.acceptance_criteria" :key="`${item.route_id}-${criterion}`">{{ criterion }}</li>
                  <li v-if="!item.acceptance_criteria.length">未填写</li>
                </ul>
              </div>
            </details>

            <div class="item-actions">
              <button class="btn-secondary" type="button" @click="handleEdit(item)">编辑</button>
              <button class="btn-secondary" type="button" @click="preparePreview(item)">预览</button>
              <button class="btn-secondary" type="button" @click="handleDuplicate(item)">复制</button>
              <button class="btn-secondary" type="button" @click="toggleActive(item)">{{ item.is_active ? '停用' : '启用' }}</button>
              <button class="btn-danger" type="button" @click="handleDelete(item)">删除</button>
            </div>
          </article>
        </section>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { learningRouteApi } from '../api'

const defaultForm = () => ({
  job_id: '',
  job_name: '',
  category: '',
  route_source: 'backoffice_learning_route',
  route_stage: '',
  stage_title: '',
  material_type: 'custom_route',
  task_type: 'case_practice',
  estimated_minutes: 120,
  keywords: [],
  learning_material: '',
  practice_task: '',
  acceptance_criteria: [],
  is_active: true,
  sort_order: 0
})

const taskTypeOptions = [
  { value: 'theory_demo', label: '理论 + Demo' },
  { value: 'demo_practice', label: 'Demo 练习' },
  { value: 'project_practice', label: '项目练习' },
  { value: 'project_review', label: '项目复盘' },
  { value: 'case_practice', label: '案例练习' },
  { value: 'document_output', label: '文档产出' },
  { value: 'scenario_practice', label: '情景演练' },
  { value: 'theory_case', label: '理论 + 场景' },
  { value: 'general_practice', label: '通用练习' }
]

const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const editingId = ref(null)
const message = ref('')
const messageType = ref('success')
const items = ref([])
const stats = ref({ total: 0, active_total: 0, job_coverage_total: 0, category_coverage_total: 0 })
const qualitySummary = ref(defaultQualitySummary())
const coverageLoading = ref(false)
const coverageSummary = ref({})
const coverageItems = ref([])
const selectedCoverageJob = ref('')
const filterOptions = ref({ job_ids: [], categories: [], task_types: [] })
const filters = ref({ job_id: '', category: '', task_type: '', is_active: '', keyword: '' })
const form = ref(defaultForm())
const importInput = ref(null)
const previewResult = ref(null)
const previewForm = ref({
  route_id: '',
  target_position: '',
  job_id: '',
  category: '',
  ability_name: '岗位能力',
  missing_keywords: [],
  include_inactive: false
})

const keywordText = computed({
  get: () => form.value.keywords.join(', '),
  set: value => { form.value.keywords = splitText(value) }
})

const criteriaText = computed({
  get: () => form.value.acceptance_criteria.join('\n'),
  set: value => { form.value.acceptance_criteria = splitLines(value) }
})

const selectedCoverage = computed(() => coverageItems.value.find(item => item.job_id === selectedCoverageJob.value) || null)

const previewKeywordsText = computed({
  get: () => previewForm.value.missing_keywords.join(', '),
  set: value => { previewForm.value.missing_keywords = splitText(value) }
})

onMounted(loadAll)

function defaultQualitySummary() {
  return {
    complete_total: 0,
    needs_improvement_total: 0,
    not_recommended_total: 0,
    missing_practice_total: 0,
    missing_acceptance_total: 0,
    missing_minutes_total: 0,
    missing_keywords_total: 0
  }
}

function splitText(value) {
  return String(value || '')
    .replace(/，/g, ',')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
}

function splitLines(value) {
  return String(value || '')
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean)
}

function taskTypeLabel(type) {
  return taskTypeOptions.find(item => item.value === type)?.label || type || '未设置'
}

function qualityLabel(item) {
  if (!item.quality_hints?.length) return '完整'
  if (item.quality_hints.includes('缺少练习任务') || item.quality_hints.includes('缺少验收方式')) return '不建议启用'
  return '需补充'
}

function apiFilters() {
  return {
    job_id: filters.value.job_id || undefined,
    category: filters.value.category || undefined,
    task_type: filters.value.task_type || undefined,
    is_active: filters.value.is_active === '' ? undefined : filters.value.is_active === 'true',
    keyword: filters.value.keyword || undefined
  }
}

async function loadAll() {
  await Promise.all([loadRoutes(), loadCoverage()])
}

async function loadRoutes() {
  loading.value = true
  try {
    const data = await learningRouteApi.list(apiFilters())
    items.value = data.items || []
    stats.value = {
      total: data.total || 0,
      active_total: data.active_total || 0,
      job_coverage_total: data.job_coverage_total || 0,
      category_coverage_total: data.category_coverage_total || 0
    }
    qualitySummary.value = { ...defaultQualitySummary(), ...(data.quality_summary || {}) }
    filterOptions.value = data.filters || { job_ids: [], categories: [], task_types: [] }
  } catch (e) {
    setMessage(e.message || '学习路线读取失败', 'error')
  } finally {
    loading.value = false
  }
}

async function loadCoverage() {
  coverageLoading.value = true
  try {
    const data = await learningRouteApi.coverage()
    coverageSummary.value = data || {}
    coverageItems.value = data.items || []
    if (!selectedCoverageJob.value && coverageItems.value.length) {
      selectedCoverageJob.value = coverageItems.value[0].job_id
    }
  } catch (e) {
    setMessage(e.message || '学习路线覆盖矩阵读取失败', 'error')
  } finally {
    coverageLoading.value = false
  }
}

function resetForm() {
  editingId.value = null
  form.value = defaultForm()
  setMessage('')
}

function startCreate() {
  resetForm()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handleEdit(item) {
  editingId.value = item.route_id
  form.value = {
    job_id: item.job_id || '',
    job_name: item.job_name || '',
    category: item.category || '',
    route_source: item.route_source || 'backoffice_learning_route',
    route_stage: item.route_stage || '',
    stage_title: item.stage_title || '',
    material_type: item.material_type || 'custom_route',
    task_type: item.task_type || 'case_practice',
    estimated_minutes: item.estimated_minutes || 120,
    keywords: item.keywords || [],
    learning_material: item.learning_material || '',
    practice_task: item.practice_task || '',
    acceptance_criteria: item.acceptance_criteria || [],
    is_active: !!item.is_active,
    sort_order: item.sort_order || 0
  }
  setMessage('')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function payload() {
  return {
    ...form.value,
    job_id: form.value.job_id || null,
    job_name: form.value.job_name || null,
    category: form.value.category || null,
    estimated_minutes: Number(form.value.estimated_minutes) || null,
    sort_order: Number(form.value.sort_order) || 0
  }
}

async function handleSubmit() {
  setMessage('')
  if (!form.value.route_source || !form.value.route_stage || !form.value.stage_title) {
    setMessage('路线来源、阶段编码和阶段名称不能为空', 'error')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await learningRouteApi.update(editingId.value, payload())
      setMessage('路线阶段已更新')
    } else {
      await learningRouteApi.create(payload())
      setMessage('路线阶段已创建')
      resetForm()
    }
    await loadAll()
  } catch (e) {
    setMessage(e.message || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function toggleActive(item) {
  const nextActive = !item.is_active
  if (nextActive && item.quality_level === 'not_recommended') {
    const reason = (item.quality_hints || []).join('、') || '质量检查未通过'
    if (!confirm(`这条路线当前为“不建议启用”：${reason}。仍然启用吗？`)) return
  }
  try {
    await learningRouteApi.update(item.route_id, { ...item, is_active: nextActive })
    await loadAll()
  } catch (e) {
    setMessage(e.message || '状态更新失败', 'error')
  }
}

async function handleDuplicate(item) {
  try {
    await learningRouteApi.duplicate(item.route_id)
    setMessage('已复制为新路线，默认停用，请编辑确认后再启用')
    await loadAll()
  } catch (e) {
    setMessage(e.message || '复制失败', 'error')
  }
}

async function handleDelete(item) {
  if (!confirm(`确定删除“${item.stage_title}”吗？`)) return
  try {
    await learningRouteApi.delete(item.route_id)
    if (editingId.value === item.route_id) resetForm()
    await loadAll()
  } catch (e) {
    setMessage(e.message || '删除失败', 'error')
  }
}

function exportRoutes() {
  const payload = {
    version: 'learning_routes_v1',
    exported_at: new Date().toISOString(),
    filters: apiFilters(),
    items: items.value
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `learning-routes-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function triggerImport() {
  importInput.value?.click()
}

async function handleImport(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  try {
    const parsed = JSON.parse(await file.text())
    if (parsed.version !== 'learning_routes_v1') {
      throw new Error('JSON 版本必须是 learning_routes_v1')
    }
    const result = await learningRouteApi.bulkUpsert(parsed)
    setMessage(`导入完成：新增 ${result.created_total || 0}，更新 ${result.updated_total || 0}`)
    await loadAll()
  } catch (e) {
    setMessage(e.message || '导入失败', 'error')
  }
}

function preparePreview(item) {
  previewForm.value = {
    route_id: item.route_id,
    target_position: item.job_name || item.job_id || '',
    job_id: item.job_id || '',
    category: item.category || '',
    ability_name: item.stage_title || '岗位能力',
    missing_keywords: item.keywords || [],
    include_inactive: !item.is_active
  }
  previewResult.value = null
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function handlePreview() {
  previewing.value = true
  previewResult.value = null
  try {
    previewResult.value = await learningRouteApi.previewTask({
      ...previewForm.value,
      route_id: Number(previewForm.value.route_id) || null
    })
  } catch (e) {
    setMessage(e.message || '任务预览失败', 'error')
  } finally {
    previewing.value = false
  }
}

function setMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
}
</script>

<style scoped>
.page {
  color: #111827;
}

.page-head,
.head-actions,
.route-head,
.form-actions,
.item-actions {
  display: flex;
  gap: 12px;
}

.page-head {
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}

.head-actions,
.form-actions,
.item-actions {
  flex-wrap: wrap;
}

.page-head h1 {
  margin: 0 0 8px;
  font-size: 22px;
}

.page-head p {
  color: #6b7280;
  line-height: 1.7;
  max-width: 760px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card,
.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
}

.stat-card {
  padding: 16px;
}

.stat-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 6px;
}

.stat-card strong {
  font-size: 26px;
}

.coverage-panel {
  padding: 18px;
  margin-bottom: 16px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.section-head h2 {
  margin: 0 0 6px;
  font-size: 18px;
}

.section-head p,
.coverage-empty {
  color: #6b7280;
  line-height: 1.7;
}

.coverage-summary,
.coverage-grid,
.ability-match-list {
  display: grid;
  gap: 10px;
}

.coverage-summary {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-bottom: 12px;
}

.coverage-summary span {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  color: #374151;
  font-size: 13px;
}

.coverage-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.coverage-card {
  text-align: left;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
  cursor: pointer;
}

.coverage-card.selected {
  border-color: #111827;
  box-shadow: inset 0 0 0 1px #111827;
}

.coverage-card strong,
.coverage-card span,
.coverage-card small {
  display: block;
}

.coverage-card span {
  margin: 6px 0;
  color: #374151;
}

.coverage-card small {
  color: #6b7280;
}

.coverage-card.good {
  background: #f0fdf4;
}

.coverage-card.needs_route {
  background: #fffbeb;
}

.coverage-card.not_recommended {
  background: #fef2f2;
}

.ability-match-panel {
  margin-top: 14px;
  border-top: 1px solid #e5e7eb;
  padding-top: 14px;
}

.ability-match-panel h3 {
  margin: 0 0 10px;
  font-size: 16px;
}

.ability-match-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.ability-match-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
}

.ability-match-item p {
  margin: 4px 0 0;
  color: #6b7280;
  line-height: 1.5;
}

.match-pill {
  align-self: flex-start;
  border-radius: 999px;
  padding: 4px 9px;
  white-space: nowrap;
  font-size: 12px;
}

.match-pill.complete {
  background: #dcfce7;
  color: #166534;
}

.match-pill.needs_improvement {
  background: #fef3c7;
  color: #92400e;
}

.match-pill.not_recommended,
.match-pill.missing {
  background: #fee2e2;
  color: #991b1b;
}

.route-layout {
  display: grid;
  grid-template-columns: minmax(360px, 440px) minmax(0, 1fr);
  gap: 16px;
}

.left-column {
  display: grid;
  gap: 16px;
  align-content: start;
}

.route-form,
.preview-panel,
.filter-panel,
.route-item,
.empty {
  padding: 18px;
}

.route-form h2,
.preview-panel h2 {
  margin: 0 0 14px;
  font-size: 18px;
}

.form-grid {
  display: grid;
  gap: 12px;
}

.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

label {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

input,
select,
textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 11px;
  color: #111827;
  font-size: 14px;
  background: #fff;
}

textarea {
  resize: vertical;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.switch-row input {
  width: auto;
}

.filter-panel {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
  margin-bottom: 12px;
}

.filter-panel label {
  margin-bottom: 0;
}

.keyword-filter {
  grid-column: span 2;
}

.route-list {
  display: grid;
  gap: 12px;
}

.route-head {
  justify-content: space-between;
}

.route-head h3,
.preview-result h3 {
  margin: 0 0 6px;
  font-size: 17px;
}

.route-head p,
.route-material,
.preview-result p {
  color: #6b7280;
  line-height: 1.6;
}

.pill-stack {
  display: grid;
  gap: 6px;
  justify-items: end;
  align-self: flex-start;
}

.status-pill,
.quality-level,
.route-meta span,
.tag,
.quality {
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
}

.status-pill.on,
.quality-level.complete,
.quality.ok {
  background: #dcfce7;
  color: #166534;
}

.status-pill.off {
  background: #f3f4f6;
  color: #4b5563;
}

.quality-level.needs_improvement,
.quality.warn {
  background: #fef3c7;
  color: #92400e;
}

.quality-level.not_recommended {
  background: #fee2e2;
  color: #991b1b;
}

.route-meta,
.tag-row,
.quality-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.route-meta span,
.tag {
  background: #f3f4f6;
  color: #374151;
}

.route-detail {
  margin: 12px 0;
  border-top: 1px solid #e5e7eb;
  padding-top: 10px;
}

.route-detail summary {
  cursor: pointer;
  font-weight: 700;
}

.route-detail p,
.route-detail li {
  color: #4b5563;
  line-height: 1.7;
}

.preview-result {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

.message {
  margin: 8px 0;
  font-size: 13px;
}

.message.success {
  color: #047857;
}

.message.error {
  color: #dc2626;
}

.empty {
  text-align: center;
  color: #6b7280;
}

.hidden-input {
  display: none;
}

@media (max-width: 1180px) {
  .route-layout,
  .stats-grid,
  .coverage-summary,
  .coverage-grid,
  .ability-match-list {
    grid-template-columns: 1fr;
  }

  .filter-panel,
  .form-grid.two {
    grid-template-columns: 1fr;
  }

  .keyword-filter {
    grid-column: span 1;
  }

  .page-head {
    display: grid;
  }
}
</style>
