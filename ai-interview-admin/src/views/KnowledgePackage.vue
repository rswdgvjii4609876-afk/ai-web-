<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>资料包预检</h1>
        <p>
          用于岗位资料、面经和能力模型正式入库前的格式检查。这里不会写入数据库，只帮助团队提前发现缺来源、缺审核状态和结构不完整的问题。
        </p>
      </div>
      <div class="head-actions">
        <button class="btn-secondary" type="button" @click="loadTemplate">载入模板</button>
        <button class="btn-secondary" type="button" @click="downloadTemplate">下载模板 JSON</button>
        <button class="btn-secondary" type="button" @click="triggerImport">载入资料包 JSON</button>
        <button class="btn-secondary" type="button" @click="saveDraft">保存草稿</button>
        <button class="btn-secondary" type="button" @click="restoreDraft">恢复草稿</button>
        <button class="btn-secondary" type="button" @click="clearDraft">清空草稿</button>
        <button class="btn-secondary" type="button" @click="exportPreflightReport">导出预检报告</button>
        <input ref="fileInput" class="hidden-input" type="file" accept="application/json,.json" @change="handleFile" />
      </div>
    </header>

    <section class="notice-card">
      <strong>当前策略</strong>
      <span>
        资料先人工总结，再统一上传。本页面只做预检和 Markdown 预览，不创建公共岗位画像，也不重建切片。
        <template v-if="hasDraft">浏览器本地已有草稿。</template>
      </span>
    </section>

    <section class="layout">
      <div class="editor-panel panel">
        <div class="section-head">
          <div>
            <h2>资料包 JSON</h2>
            <p>版本字段使用 <code>knowledge_package_v1</code>。每个岗位建议包含岗位要求、问答经验、能力模型和面试追问。</p>
          </div>
          <button class="btn-primary" type="button" @click="validatePackage">预检资料包</button>
        </div>
        <textarea v-model="rawJson" spellcheck="false" class="json-editor" placeholder="粘贴资料包 JSON，或点击右上角载入模板。"></textarea>
        <p v-if="message" :class="['message', messageType]">{{ message }}</p>
      </div>

      <aside class="summary-panel">
        <div class="stat-card"><span>岗位条目</span><strong>{{ summary.total }}</strong></div>
        <div class="stat-card"><span>可入库面经</span><strong>{{ summary.approved }}</strong></div>
        <div class="stat-card"><span>待核验</span><strong>{{ summary.pending }}</strong></div>
        <div class="stat-card"><span>错误</span><strong>{{ issues.errors.length }}</strong></div>
        <div class="stat-card"><span>提醒</span><strong>{{ issues.warnings.length }}</strong></div>
      </aside>
    </section>

    <section v-if="issues.errors.length || issues.warnings.length" class="issues-grid">
      <div class="panel issue-panel">
        <h2>错误</h2>
        <p v-if="!issues.errors.length" class="empty">暂无错误。</p>
        <ul v-else>
          <li v-for="issue in issues.errors" :key="issue">{{ issue }}</li>
        </ul>
      </div>
      <div class="panel issue-panel">
        <h2>提醒</h2>
        <p v-if="!issues.warnings.length" class="empty">暂无提醒。</p>
        <ul v-else>
          <li v-for="issue in issues.warnings" :key="issue">{{ issue }}</li>
        </ul>
      </div>
    </section>

    <section v-if="items.length" class="preview-grid">
      <div class="panel item-list">
        <div class="section-head">
          <div>
            <h2>岗位条目</h2>
            <p>选择一个岗位查看可复制的 Markdown 入库预览。</p>
          </div>
        </div>
        <button
          v-for="(item, index) in items"
          :key="`${item.title}-${index}`"
          type="button"
          :class="['item-card', selectedIndex === index ? 'selected' : '']"
          @click="selectedIndex = index"
        >
          <strong>{{ item.title || '未命名岗位资料' }}</strong>
          <span>{{ item.target_position || '未填写目标岗位' }}</span>
          <small>
            面经 {{ normalizedExperiences(item).length }} 条 ·
            分区 {{ sectionCompletion(item).completed }}/{{ sectionCompletion(item).total }}
          </small>
        </button>
      </div>

      <div class="panel markdown-panel">
        <div class="section-head">
          <div>
            <h2>Markdown 预览</h2>
            <p>后续正式入库时，可复制到公共岗位画像的“岗位画像内容”。</p>
          </div>
          <button class="btn-secondary" type="button" @click="copyMarkdown">复制 Markdown</button>
        </div>
        <pre>{{ selectedMarkdown }}</pre>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const fileInput = ref(null)
const rawJson = ref('')
const parsed = ref(null)
const items = ref([])
const issues = ref({ errors: [], warnings: [] })
const selectedIndex = ref(0)
const message = ref('')
const messageType = ref('success')
const hasDraft = ref(false)

const AUDIT_STATUSES = ['可入库', '仅参考', '待核验', '不采用']
const DRAFT_KEY = 'zhiqizhice:knowledge-package-draft:v1'

const templatePackage = {
  version: 'knowledge_package_v1',
  description: '岗位资料正式入库前的整理包。本模板只用于预检，不会自动写入数据库。',
  items: [
    {
      title: 'Python后端开发工程师岗位资料包',
      target_position: 'Python后端开发工程师',
      sections: {
        job_requirements: '硬性要求：Python 基础、Web API、数据库、缓存、接口调试。\n加分项：Docker、Celery、线上排障、RAG/LLM 工程接入。\n公司侧重点：按后续人工资料补充。',
        ability_model: '能力项：Python 基础、接口设计、数据库使用、缓存理解、异步任务、排障复盘。',
        followup_rules: '简历只声明掌握但缺少项目证据时，优先追问真实使用场景、责任边界和排障经历。'
      },
      interview_experiences: [
        {
          question: '你在项目中如何设计一个接口的异常处理和返回结构？',
          answer_points: '说明状态码、错误码、日志、参数校验、幂等和调用方体验。',
          reflection: '避免只讲框架语法，要补充真实项目中的取舍和排障。',
          company_context: '后端接口设计',
          ability: '接口设计与工程化表达',
          difficulty: '中等',
          source: '人工整理，待补具体来源链接或访谈记录',
          audit_status: '待核验'
        }
      ],
      focus_points: '接口设计、数据库索引与事务、缓存一致性、异步任务、项目排障。',
      interviewer_prompt: '回答停留在概念时继续追问项目证据；不得把简历声明直接当作掌握证明。'
    }
  ]
}

const summary = computed(() => {
  const allExperiences = items.value.flatMap(item => normalizedExperiences(item))
  return {
    total: items.value.length,
    approved: allExperiences.filter(item => item.audit_status === '可入库').length,
    pending: allExperiences.filter(item => item.audit_status === '待核验').length
  }
})

const selectedItem = computed(() => items.value[selectedIndex.value] || null)
const selectedMarkdown = computed(() => selectedItem.value ? buildMarkdown(selectedItem.value) : '')

onMounted(() => {
  refreshDraftState()
})

function setMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
}

function loadTemplate() {
  rawJson.value = JSON.stringify(templatePackage, null, 2)
  validatePackage()
}

function downloadTemplate() {
  downloadJson(templatePackage, `knowledge-package-template-${new Date().toISOString().slice(0, 10)}.json`)
}

function saveDraft() {
  const content = rawJson.value.trim()
  if (!content) {
    setMessage('当前没有可保存的资料包草稿。', 'error')
    return
  }
  localStorage.setItem(DRAFT_KEY, rawJson.value)
  refreshDraftState()
  setMessage('资料包草稿已保存到当前浏览器。')
}

function restoreDraft() {
  const draft = localStorage.getItem(DRAFT_KEY)
  if (!draft) {
    setMessage('当前浏览器没有资料包草稿。', 'error')
    return
  }
  rawJson.value = draft
  validatePackage()
  setMessage('已恢复本地资料包草稿。')
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
  refreshDraftState()
  setMessage('本地资料包草稿已清空。')
}

function refreshDraftState() {
  hasDraft.value = Boolean(localStorage.getItem(DRAFT_KEY))
}

function exportPreflightReport() {
  if (!items.value.length && !issues.value.errors.length) {
    setMessage('请先载入并预检资料包，再导出报告。', 'error')
    return
  }
  const report = buildPreflightReport()
  downloadJson(report, `knowledge-package-preflight-${new Date().toISOString().slice(0, 10)}.json`)
  setMessage('预检报告已导出。')
}

function triggerImport() {
  fileInput.value?.click()
}

function handleFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    rawJson.value = String(reader.result || '')
    validatePackage()
  }
  reader.readAsText(file, 'utf-8')
  event.target.value = ''
}

function validatePackage() {
  const nextIssues = { errors: [], warnings: [] }
  let data = null
  try {
    data = JSON.parse(rawJson.value)
  } catch (error) {
    parsed.value = null
    items.value = []
    issues.value = { errors: [`JSON 解析失败：${error.message}`], warnings: [] }
    setMessage('资料包格式不是合法 JSON。', 'error')
    return
  }

  const packageItems = Array.isArray(data?.items) ? data.items : []
  if (data?.version !== 'knowledge_package_v1') {
    nextIssues.warnings.push('建议将 version 设置为 knowledge_package_v1，便于后续批量入库时识别版本。')
  }
  if (!packageItems.length) {
    nextIssues.errors.push('items 不能为空，至少需要 1 个岗位资料条目。')
  }

  packageItems.forEach((item, index) => validateItem(item, index, nextIssues))

  parsed.value = data
  items.value = packageItems
  selectedIndex.value = Math.min(selectedIndex.value, Math.max(packageItems.length - 1, 0))
  issues.value = nextIssues

  if (nextIssues.errors.length) {
    setMessage(`预检完成：发现 ${nextIssues.errors.length} 个错误，暂不建议入库。`, 'error')
  } else {
    setMessage(`预检完成：${packageItems.length} 个岗位条目可进入人工复核。`, 'success')
  }
}

function buildPreflightReport() {
  return {
    version: 'knowledge_package_preflight_report_v1',
    generated_at: new Date().toISOString(),
    package_version: parsed.value?.version || '',
    summary: summary.value,
    errors: issues.value.errors,
    warnings: issues.value.warnings,
    items: items.value.map((item, index) => {
      const experiences = normalizedExperiences(item)
      const completion = sectionCompletion(item)
      return {
        index: index + 1,
        title: item.title || '',
        target_position: item.target_position || '',
        section_completion: completion,
        interview_experience_total: experiences.length,
        approved_experience_total: experiences.filter(exp => exp.audit_status === '可入库').length,
        pending_experience_total: experiences.filter(exp => exp.audit_status === '待核验').length,
        reference_only_total: experiences.filter(exp => exp.audit_status === '仅参考').length,
        rejected_total: experiences.filter(exp => exp.audit_status === '不采用').length,
        missing_source_total: experiences.filter(exp => !exp.source).length,
        markdown_preview: buildMarkdown(item)
      }
    })
  }
}

function validateItem(item, index, nextIssues) {
  const prefix = `第 ${index + 1} 条`
  if (!clean(item.title)) nextIssues.errors.push(`${prefix} 缺少 title。`)
  if (!clean(item.target_position)) nextIssues.errors.push(`${prefix} 缺少 target_position。`)

  const completion = sectionCompletion(item)
  if (completion.completed < 2) {
    nextIssues.warnings.push(`${prefix} 知识库分区填写较少，建议至少补岗位要求和面试追问。`)
  }

  const experiences = normalizedExperiences(item)
  if (!experiences.length) {
    nextIssues.warnings.push(`${prefix} 暂无结构化问答经验。`)
  }
  experiences.forEach((experience, expIndex) => {
    const expPrefix = `${prefix} 第 ${expIndex + 1} 条面经`
    if (!clean(experience.question)) nextIssues.errors.push(`${expPrefix} 缺少真实问题。`)
    if (!clean(experience.answer_points)) nextIssues.warnings.push(`${expPrefix} 缺少参考回答要点。`)
    if (!clean(experience.source)) nextIssues.warnings.push(`${expPrefix} 缺少来源说明。`)
    if (!AUDIT_STATUSES.includes(experience.audit_status)) {
      nextIssues.errors.push(`${expPrefix} 审核状态必须是：${AUDIT_STATUSES.join(' / ')}。`)
    }
    if (clean(experience.audit_status) === '可入库' && !clean(experience.source)) {
      nextIssues.errors.push(`${expPrefix} 标记为可入库时必须写来源说明。`)
    }
  })
}

function normalizedExperiences(item) {
  const fromRoot = Array.isArray(item?.interview_experiences) ? item.interview_experiences : []
  const fromSection = Array.isArray(item?.sections?.interview_experience) ? item.sections.interview_experience : []
  return [...fromRoot, ...fromSection].map(experience => ({
    question: clean(experience.question),
    answer_points: clean(experience.answer_points || experience.answer),
    reflection: clean(experience.reflection),
    company_context: clean(experience.company_context || experience.scene),
    ability: clean(experience.ability),
    difficulty: clean(experience.difficulty || '中等'),
    source: clean(experience.source),
    audit_status: clean(experience.audit_status || '待核验')
  }))
}

function sectionCompletion(item) {
  const sections = item?.sections || {}
  const values = [
    sections.job_requirements,
    normalizedExperiences(item).length ? 'has_experience' : '',
    sections.ability_model,
    sections.followup_rules
  ]
  return { total: 4, completed: values.filter(value => clean(value)).length }
}

function buildMarkdown(item) {
  const sections = item.sections || {}
  const lines = [
    `## 岗位要求`,
    clean(sections.job_requirements) || '待补充岗位硬性要求、加分项和公司侧重点。',
    '',
    `## 问答经验`
  ]

  const experiences = normalizedExperiences(item)
  if (!experiences.length) {
    lines.push('待补充结构化问答经验。')
  } else {
    experiences.forEach((experience, index) => {
      lines.push(
        `### 问答经验 ${index + 1}`,
        `- 真实问题：${experience.question || '待补充'}`,
        `- 参考回答要点：${experience.answer_points || '待补充'}`,
        `- 复盘反思：${experience.reflection || '待补充'}`,
        `- 公司/场景：${experience.company_context || '待补充'}`,
        `- 考察能力：${experience.ability || '待补充'}`,
        `- 难度：${experience.difficulty || '中等'}`,
        `- 来源说明：${experience.source || '待补充'}`,
        `- 审核状态：${experience.audit_status || '待核验'}`,
        ''
      )
    })
  }

  lines.push(
    `## 能力模型`,
    clean(sections.ability_model) || '待补充能力项、等级标准、权重和证据线索。',
    '',
    `## 面试追问`,
    clean(sections.followup_rules) || '待补充证据追问规则、评分关注点和追问边界。'
  )

  return lines.join('\n')
}

async function copyMarkdown() {
  if (!selectedMarkdown.value) return
  try {
    await navigator.clipboard.writeText(selectedMarkdown.value)
    setMessage('Markdown 已复制，可粘贴到公共岗位画像编辑区。')
  } catch {
    setMessage('浏览器不允许自动复制，请手动选中 Markdown 复制。', 'error')
  }
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

function clean(value) {
  return String(value || '').trim()
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-head,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-head h1,
.section-head h2 {
  margin: 0 0 8px;
  color: #111827;
}

.page-head p,
.section-head p {
  margin: 0;
  color: #6b7280;
  line-height: 1.7;
  font-size: 14px;
}

.head-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.panel,
.notice-card,
.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.notice-card {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  color: #374151;
}

.notice-card strong {
  color: #111827;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 18px;
}

.editor-panel,
.issue-panel,
.item-list,
.markdown-panel {
  padding: 18px;
}

.json-editor {
  width: 100%;
  min-height: 420px;
  margin-top: 16px;
  padding: 14px;
  resize: vertical;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #111827;
  background: #f9fafb;
}

.summary-panel {
  display: grid;
  gap: 12px;
}

.stat-card {
  padding: 14px;
}

.stat-card span {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 8px;
  color: #111827;
  font-size: 28px;
}

.issues-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.issue-panel h2 {
  margin: 0 0 12px;
}

.issue-panel ul {
  margin: 0;
  padding-left: 18px;
  color: #374151;
  line-height: 1.7;
}

.preview-grid {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.item-card {
  width: 100%;
  text-align: left;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  padding: 12px;
  cursor: pointer;
}

.item-card.selected {
  background: #111827;
  color: #fff;
  border-color: #111827;
}

.item-card strong,
.item-card span,
.item-card small {
  display: block;
}

.item-card span {
  margin-top: 4px;
  color: inherit;
  opacity: 0.78;
}

.item-card small {
  margin-top: 8px;
  color: inherit;
  opacity: 0.7;
}

.markdown-panel pre {
  white-space: pre-wrap;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  line-height: 1.7;
  color: #111827;
  max-height: 620px;
  overflow: auto;
}

.btn-primary,
.btn-secondary {
  border: 1px solid #111827;
  border-radius: 8px;
  padding: 9px 13px;
  cursor: pointer;
  font-weight: 600;
}

.btn-primary {
  background: #111827;
  color: #fff;
}

.btn-secondary {
  background: #fff;
  color: #111827;
}

.hidden-input {
  display: none;
}

.message {
  margin: 12px 0 0;
  font-weight: 600;
  font-size: 14px;
}

.message.success {
  color: #047857;
}

.message.error {
  color: #b91c1c;
}

.empty {
  color: #6b7280;
}

@media (max-width: 1100px) {
  .layout,
  .issues-grid,
  .preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
