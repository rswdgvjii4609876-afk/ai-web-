<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:20px">
      <div>
        <h1 style="font-size:20px;margin-bottom:8px">公共岗位画像库</h1>
        <p style="color:#6b7280;font-size:14px;line-height:1.7">
          这里维护系统可复用的公共岗位画像和岗位知识库。管理员可以查看岗位要求、问答经验、能力模型与面试追问，并管理知识切片。
        </p>
      </div>
      <button class="btn-primary" @click="startCreate">{{ editingId ? '新建一份' : '+ 新建公共岗位画像' }}</button>
    </div>

    <div class="summary-grid">
      <div class="card summary-card">
        <span>公共岗位画像</span>
        <strong>{{ stats.total }}</strong>
      </div>
      <div class="card summary-card">
        <span>启用中</span>
        <strong>{{ stats.active }}</strong>
      </div>
      <div class="card summary-card">
        <span>技术岗画像</span>
        <strong>{{ stats.tech }}</strong>
      </div>
      <div class="card summary-card">
        <span>非技术岗画像</span>
        <strong>{{ stats.nonTech }}</strong>
      </div>
      <div class="card summary-card">
        <span>知识切片</span>
        <strong>{{ stats.slices }}</strong>
      </div>
    </div>

    <div class="kb-layout">
      <div class="card">
        <h3 style="margin-bottom:16px">{{ editingId ? '编辑公共岗位画像' : '新建公共岗位画像' }}</h3>

        <div class="form-group">
          <label>标题</label>
          <input v-model="form.title" placeholder="例如：Python后端开发工程师岗位画像" />
        </div>

        <div class="form-group">
          <label>目标岗位</label>
          <input v-model="form.target_position" placeholder="例如：Python后端开发工程师" />
        </div>

        <div class="section-editor">
          <div class="section-editor-head">
            <div>
              <h4>岗位知识库分区</h4>
              <p>按分区维护知识资产，保存时会自动合成为 Markdown 写入岗位画像内容。</p>
            </div>
            <span class="section-completion">{{ formCompletion.completed }} / {{ formCompletion.total }} 已填写</span>
          </div>

          <div v-for="section in formSections" :key="section.key" class="form-group section-field">
            <label>{{ section.label }}</label>
            <textarea
              v-model="form.sections[section.key]"
              :rows="section.rows"
              :placeholder="section.placeholder"
            />
          </div>

          <div v-if="form.legacy_content" class="form-group section-field legacy-field">
            <label>旧格式原文</label>
            <textarea
              v-model="form.legacy_content"
              rows="5"
              placeholder="无法自动拆分的旧内容会保留在这里，保存时写入“其他内容”分区。"
            />
          </div>
        </div>

        <div class="form-group">
          <label>重点测评方向</label>
          <textarea v-model="form.focus_points" rows="5" placeholder="例如：技术岗追问语言基础、数据库、Redis、HTTP、并发、系统设计；职能岗追问流程、数据、沟通和复盘" />
        </div>

        <div class="form-group">
          <label>额外面试官要求</label>
          <textarea v-model="form.interviewer_prompt" rows="4" placeholder="例如：回答模糊时继续追问证据，最终建议必须具体可执行" />
        </div>

        <label class="switch-row">
          <input v-model="form.is_active" type="checkbox" />
          <span>启用这份公共岗位画像</span>
        </label>

        <p v-if="msg" :class="msg.startsWith('✅') ? 'success-text' : 'error-text'">{{ msg }}</p>

        <div style="display:flex;gap:10px;margin-top:12px">
          <button class="btn-primary" @click="handleSubmit" :disabled="saving">
            {{ saving ? '保存中...' : (editingId ? '保存修改' : '创建公共岗位画像') }}
          </button>
          <button v-if="editingId" class="btn-sm" @click="resetForm">取消编辑</button>
        </div>
      </div>

      <div>
        <div class="card" style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
            <h3>公共岗位画像列表 <span class="count-text">当前显示 {{ filteredItems.length }} / {{ items.length }}</span></h3>
            <input v-model="keyword" placeholder="按标题 / 岗位筛选" style="width:260px" />
          </div>
        </div>

        <div v-if="loading" class="card empty-card">加载中...</div>

        <div v-else-if="filteredItems.length === 0" class="card empty-card">
          还没有公共岗位画像。
        </div>

        <div v-else class="kb-list">
          <div v-for="item in filteredItems" :key="item.knowledge_base_id" class="card kb-item">
            <div class="kb-head">
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.target_position }}</p>
              </div>
              <span :class="['badge', item.is_active ? 'badge-green' : 'badge-red']">
                {{ item.is_active ? '启用中' : '已停用' }}
              </span>
            </div>

            <p class="kb-preview">{{ knowledgePreviewText(item) }}</p>

            <div class="asset-tags">
              <span class="asset-tag">分区 {{ sectionCompletion(item).completed }}/{{ sectionCompletion(item).total }}</span>
              <span class="asset-tag">问答经验 {{ interviewExperienceCount(item) }}</span>
              <span :class="['asset-tag', hasCompanyFocus(item) ? 'asset-ok' : 'asset-warn']">
                {{ hasCompanyFocus(item) ? '已写公司侧重点' : '未写公司侧重点' }}
              </span>
              <span
                v-for="status in auditStatuses(item)"
                :key="`${item.knowledge_base_id}-${status}`"
                :class="['asset-tag', auditStatusClass(status)]"
              >
                {{ status }}
              </span>
            </div>

            <p v-if="item.focus_points" class="kb-extra"><strong>测评重点：</strong>{{ item.focus_points }}</p>
            <p v-if="item.interviewer_prompt" class="kb-extra"><strong>面试官要求：</strong>{{ item.interviewer_prompt }}</p>

            <div class="kb-footer">
              <span>
                更新时间：{{ formatDate(item.updated_at || item.created_at) }}
                <span class="slice-count">切片 {{ item.slice_count ?? '-' }}</span>
              </span>
              <div style="display:flex;gap:8px">
                <button class="btn-sm" @click="toggleDetails(item)">
                  {{ expandedIds.has(item.knowledge_base_id) ? '收起内容' : '查看内容' }}
                </button>
                <button class="btn-sm" :disabled="sliceLoading[item.knowledge_base_id]" @click="handleRebuildSlices(item)">
                  {{ sliceLoading[item.knowledge_base_id] ? '处理中...' : '重建切片' }}
                </button>
                <button class="btn-primary btn-sm" @click="handleEdit(item)">编辑</button>
                <button class="btn-danger btn-sm" @click="handleDelete(item)">删除</button>
              </div>
            </div>

            <div v-if="expandedIds.has(item.knowledge_base_id)" class="kb-detail">
              <div>
                <div class="detail-label">结构化岗位知识库</div>
                <div v-if="structuredSections(item.knowledge_content).length" class="structured-section-list">
                  <div v-for="section in structuredSections(item.knowledge_content)" :key="`${item.knowledge_base_id}-${section.key}`" class="structured-section">
                    <div class="structured-section-title">{{ section.title }}</div>
                    <pre>{{ section.content }}</pre>
                  </div>
                </div>
                <pre v-else>{{ item.knowledge_content }}</pre>
              </div>
              <div v-if="sliceError[item.knowledge_base_id]" class="error-text">
                {{ sliceError[item.knowledge_base_id] }}
              </div>
              <div v-else-if="sliceLoading[item.knowledge_base_id]" class="helper-text">正在加载知识切片...</div>
              <div v-else>
                <div class="detail-label">知识切片 {{ slicesByKb[item.knowledge_base_id]?.length || 0 }}</div>
                <div v-if="!(slicesByKb[item.knowledge_base_id]?.length)" class="helper-text">
                  暂无切片，可点击“重建切片”生成。
                </div>
                <div v-else class="slice-list">
                  <div v-for="slice in slicesByKb[item.knowledge_base_id]" :key="slice.slice_id" class="slice-item">
                    <div class="slice-head">
                      <strong>{{ slice.title || '岗位画像切片' }}</strong>
                      <span>{{ sourceSectionLabel(slice.source_section) }} / {{ slice.difficulty }}</span>
                    </div>
                    <p>{{ slice.content }}</p>
                    <div class="tag-row">
                      <span v-for="tag in compactTags(slice)" :key="`${slice.slice_id}-${tag}`" class="tag">{{ tag }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { knowledgeBaseApi } from '../api'

const loading = ref(true)
const saving = ref(false)
const keyword = ref('')
const editingId = ref(null)
const msg = ref('')
const items = ref([])

const emptySections = () => ({
  job_requirements: '',
  interview_experience: '',
  ability_model: '',
  followup_rules: ''
})

const defaultForm = () => ({
  title: '',
  target_position: '',
  sections: emptySections(),
  legacy_content: '',
  focus_points: '',
  interviewer_prompt: '',
  is_active: true
})

const form = ref(defaultForm())

const techKeywords = ['python', 'java', '前端', '后端', '开发', '测试', '算法', '数据分析', '工程师', 'typescript', 'react', 'vue']
const sectionLabels = {
  job_requirements: '岗位要求',
  interview_experience: '问答经验',
  ability_model: '能力模型',
  followup_rules: '面试追问',
  knowledge_content: '其他内容',
  focus_points: '训练重点',
  interviewer_prompt: '面试官要求',
  overview: '岗位概览'
}
const formSections = [
  {
    key: 'job_requirements',
    label: '岗位要求',
    rows: 7,
    placeholder: '- 硬性要求：\n- 加分项：\n- 公司侧重点：例如大厂更看重项目深度，中小团队更看重落地速度\n- 来源与许可：可入库 / 仅参考 / 不采用 / 待核验'
  },
  {
    key: 'interview_experience',
    label: '问答经验',
    rows: 8,
    placeholder: '- 问题：\n  参考回答要点：\n  复盘反思：\n  来源与审核状态：待核验'
  },
  {
    key: 'ability_model',
    label: '能力模型',
    rows: 7,
    placeholder: '- 能力项：要求等级 / 权重 / 证据线索 / 可提升系数\n- 示例：接口设计：4 / 0.18 / REST API、鉴权、错误处理 / 1.2'
  },
  {
    key: 'followup_rules',
    label: '面试追问',
    rows: 7,
    placeholder: '- 证据追问规则：回答模糊时追问项目背景、个人职责、指标结果\n- 评分关注点：基础是否扎实、证据是否真实、能否定位问题'
  }
]
const sectionHeadingMap = {
  岗位要求: 'job_requirements',
  问答经验: 'interview_experience',
  能力模型: 'ability_model',
  面试追问: 'followup_rules',
  其他内容: 'legacy_content'
}
const auditStatusOptions = ['可入库', '仅参考', '不采用', '待核验']

const formCompletion = computed(() => {
  const total = formSections.length
  const completed = formSections.filter(section => form.value.sections[section.key]?.trim()).length
  return { total, completed }
})

const stats = computed(() => {
  const total = items.value.length
  const active = items.value.filter(item => item.is_active).length
  const tech = items.value.filter(item => isTechProfile(item)).length
  const slices = items.value.reduce((sum, item) => sum + Number(item.slice_count || 0), 0)
  return { total, active, tech, nonTech: total - tech, slices }
})

const filteredItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(item => {
    return [item.title, item.target_position, item.preview, item.knowledge_content]
      .filter(Boolean)
      .some(text => text.toLowerCase().includes(kw))
  })
})

const expandedIds = ref(new Set())
const slicesByKb = ref({})
const sliceLoading = ref({})
const sliceError = ref({})

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN')
}

function isTechProfile(item) {
  const text = `${item.title || ''} ${item.target_position || ''}`.toLowerCase()
  return techKeywords.some(keyword => text.includes(keyword.toLowerCase()))
}

function compactTags(slice) {
  return [
    ...(slice.stage_tags || []),
    ...(slice.skill_tags || []),
    ...(slice.scene_tags || [])
  ].filter(Boolean).slice(0, 6)
}

function sourceSectionLabel(value) {
  return sectionLabels[value] || value || '切片'
}

function parseKnowledgeSections(text) {
  const content = String(text || '')
  const result = {
    sections: emptySections(),
    legacy_content: ''
  }
  const matches = [...content.matchAll(/^#{1,4}\s*(岗位要求|问答经验|能力模型|面试追问|其他内容)\s*$/gm)]
  if (!matches.length) {
    result.legacy_content = content.trim()
    return result
  }

  const beforeFirst = content.slice(0, matches[0].index).trim()
  if (beforeFirst) result.legacy_content = beforeFirst

  matches.forEach((match, index) => {
    const start = match.index + match[0].length
    const end = matches[index + 1]?.index ?? content.length
    const title = match[1]
    const key = sectionHeadingMap[title]
    const value = content.slice(start, end).trim()
    if (key === 'legacy_content') {
      result.legacy_content = [result.legacy_content, value].filter(Boolean).join('\n\n')
    } else if (key) {
      result.sections[key] = value
    }
  })

  return result
}

function structuredSections(text) {
  const parsed = parseKnowledgeSections(text)
  const sections = formSections
    .map(section => ({
      key: section.key,
      title: section.label,
      content: parsed.sections[section.key]?.trim() || ''
    }))
    .filter(item => item.content)

  if (parsed.legacy_content?.trim()) {
    sections.push({
      key: 'legacy_content',
      title: '其他内容',
      content: parsed.legacy_content.trim()
    })
  }

  return sections
}

function buildKnowledgeContent() {
  const parts = formSections
    .map(section => ({
      title: section.label,
      content: form.value.sections[section.key]?.trim() || ''
    }))
    .filter(section => section.content)
    .map(section => `## ${section.title}\n${section.content}`)

  const legacy = form.value.legacy_content?.trim()
  if (legacy) parts.push(`## 其他内容\n${legacy}`)
  return parts.join('\n\n')
}

function sectionCompletion(item) {
  const parsed = parseKnowledgeSections(item.knowledge_content)
  const total = formSections.length
  const completed = formSections.filter(section => parsed.sections[section.key]?.trim()).length
  return { total, completed }
}

function interviewExperienceCount(item) {
  const content = parseKnowledgeSections(item.knowledge_content).sections.interview_experience || ''
  const matches = content.match(/问题[:：]|Q\d+|面试题|追问/g)
  if (matches?.length) return matches.length
  return content.trim() ? 1 : 0
}

function hasCompanyFocus(item) {
  const content = parseKnowledgeSections(item.knowledge_content).sections.job_requirements || ''
  return /公司侧重点|公司要求|大厂|中小|互联网|国企|外企|创业公司|行业侧重点/.test(content)
}

function auditStatuses(item) {
  const content = String(item.knowledge_content || '')
  const matched = auditStatusOptions.filter(status => content.includes(status))
  return matched.length ? matched : ['待核验']
}

function auditStatusClass(status) {
  return {
    可入库: 'asset-ok',
    仅参考: 'asset-info',
    不采用: 'asset-bad',
    待核验: 'asset-warn'
  }[status] || 'asset-warn'
}

function formFromKnowledgeBase(item) {
  const parsed = parseKnowledgeSections(item.knowledge_content)
  return {
    title: item.title || '',
    target_position: item.target_position || '',
    sections: {
      ...emptySections(),
      ...parsed.sections
    },
    legacy_content: parsed.legacy_content || '',
    focus_points: item.focus_points || '',
    interviewer_prompt: item.interviewer_prompt || '',
    is_active: !!item.is_active
  }
}

function knowledgePreviewText(item) {
  const sections = structuredSections(item.knowledge_content)
  if (sections.length) {
    return sections
      .slice(0, 2)
      .map(section => `${section.title}：${section.content.replace(/\s+/g, ' ').slice(0, 80)}`)
      .join(' / ')
  }
  return item.preview || ''
}

async function loadItems() {
  loading.value = true
  try {
    const data = await knowledgeBaseApi.list()
    items.value = data.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadSlices(item, force = false) {
  const id = item.knowledge_base_id
  if (!force && slicesByKb.value[id]) return
  sliceLoading.value = { ...sliceLoading.value, [id]: true }
  sliceError.value = { ...sliceError.value, [id]: '' }
  try {
    const data = await knowledgeBaseApi.slices(id)
    slicesByKb.value = { ...slicesByKb.value, [id]: data.items || [] }
  } catch (e) {
    sliceError.value = { ...sliceError.value, [id]: e.message || '加载知识切片失败' }
  } finally {
    sliceLoading.value = { ...sliceLoading.value, [id]: false }
  }
}

async function toggleDetails(item) {
  const next = new Set(expandedIds.value)
  if (next.has(item.knowledge_base_id)) {
    next.delete(item.knowledge_base_id)
    expandedIds.value = next
    return
  }
  next.add(item.knowledge_base_id)
  expandedIds.value = next
  await loadSlices(item)
}

async function handleRebuildSlices(item) {
  const id = item.knowledge_base_id
  sliceLoading.value = { ...sliceLoading.value, [id]: true }
  sliceError.value = { ...sliceError.value, [id]: '' }
  try {
    const data = await knowledgeBaseApi.rebuildSlices(id)
    slicesByKb.value = { ...slicesByKb.value, [id]: data.items || [] }
    items.value = items.value.map(kb => kb.knowledge_base_id === id ? { ...kb, slice_count: data.total } : kb)
    const next = new Set(expandedIds.value)
    next.add(id)
    expandedIds.value = next
  } catch (e) {
    sliceError.value = { ...sliceError.value, [id]: e.message || '切片重建失败' }
  } finally {
    sliceLoading.value = { ...sliceLoading.value, [id]: false }
  }
}

function resetForm() {
  editingId.value = null
  form.value = defaultForm()
  msg.value = ''
}

function startCreate() {
  resetForm()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handleEdit(item) {
  editingId.value = item.knowledge_base_id
  form.value = formFromKnowledgeBase(item)
  msg.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function handleSubmit() {
  msg.value = ''
  const knowledgeContent = buildKnowledgeContent()
  if (!form.value.title.trim() || !form.value.target_position.trim() || !knowledgeContent.trim()) {
    msg.value = '标题、目标岗位和至少一个知识库分区不能为空'
    return
  }

  saving.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      target_position: form.value.target_position.trim(),
      knowledge_content: knowledgeContent.trim(),
      focus_points: form.value.focus_points.trim(),
      interviewer_prompt: form.value.interviewer_prompt.trim(),
      is_active: form.value.is_active
    }

    if (editingId.value) {
      await knowledgeBaseApi.update(editingId.value, payload)
      await loadItems()
      msg.value = '✅ 公共岗位画像已更新'
    } else {
      await knowledgeBaseApi.create(payload)
      await loadItems()
      resetForm()
      msg.value = '✅ 公共岗位画像已创建'
    }
  } catch (e) {
    msg.value = e.message
  } finally {
    saving.value = false
  }
}

async function handleDelete(item) {
  if (!confirm(`确定删除“${item.title}”吗？`)) return
  try {
    await knowledgeBaseApi.delete(item.knowledge_base_id)
    if (editingId.value === item.knowledge_base_id) resetForm()
    await loadItems()
  } catch (e) {
    alert('删除失败：' + e.message)
  }
}

onMounted(loadItems)
</script>

<style scoped>
.kb-layout {
  display: grid;
  grid-template-columns: minmax(0, 420px) minmax(0, 1fr);
  gap: 16px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.summary-card {
  padding: 16px;
}
.summary-card span {
  display: block;
  color: #6b7280;
  font-size: 12px;
  margin-bottom: 6px;
}
.summary-card strong {
  color: #111827;
  font-size: 24px;
}
.count-text {
  color: #6b7280;
  font-size: 12px;
  font-weight: 400;
  margin-left: 8px;
}
.form-group {
  margin-bottom: 14px;
}
.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
}
.form-group input,
.form-group textarea {
  width: 100%;
}
.form-group textarea {
  resize: vertical;
}
.section-editor {
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}
.section-editor-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.section-editor-head h4 {
  color: #111827;
  font-size: 15px;
  margin-bottom: 4px;
}
.section-editor-head p {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}
.section-completion {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #111827;
  font-size: 12px;
  font-weight: 700;
}
.section-field textarea {
  background: #fff;
}
.legacy-field textarea {
  background: #fffbeb;
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  margin-top: 6px;
}
.switch-row input {
  width: auto;
}
.success-text {
  color: #059669;
  font-size: 13px;
}
.error-text {
  color: #ef4444;
  font-size: 13px;
}
.kb-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kb-item {
  padding: 18px;
}
.kb-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.kb-head h3 {
  font-size: 17px;
  margin-bottom: 6px;
}
.kb-head p {
  color: #6b7280;
  font-size: 14px;
}
.kb-preview {
  margin: 14px 0;
  line-height: 1.8;
}
.asset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0 12px;
}
.asset-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 12px;
  font-weight: 600;
}
.asset-ok {
  background: #d1fae5;
  color: #065f46;
}
.asset-warn {
  background: #fef3c7;
  color: #92400e;
}
.asset-info {
  background: #dbeafe;
  color: #1d4ed8;
}
.asset-bad {
  background: #fee2e2;
  color: #991b1b;
}
.kb-extra {
  font-size: 14px;
  line-height: 1.7;
  color: #4b5563;
  margin-top: 10px;
}
.kb-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  color: #6b7280;
  font-size: 13px;
}
.slice-count {
  margin-left: 10px;
  color: #0f766e;
  font-weight: 600;
}
.kb-detail {
  margin-top: 16px;
  border-top: 1px solid #e5e7eb;
  padding-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.detail-label {
  color: #374151;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
}
.kb-detail pre {
  white-space: pre-wrap;
  word-break: break-word;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  line-height: 1.75;
  font-family: inherit;
  font-size: 13px;
  color: #374151;
}
.structured-section-list {
  display: grid;
  gap: 10px;
}
.structured-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.structured-section-title {
  padding: 8px 12px;
  background: #f3f4f6;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}
.structured-section pre {
  border: 0;
  border-radius: 0;
  margin: 0;
  background: #fff;
}
.slice-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.slice-item {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}
.slice-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
}
.slice-head span {
  color: #6b7280;
  white-space: nowrap;
}
.slice-item p {
  color: #4b5563;
  line-height: 1.7;
  font-size: 13px;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.tag {
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  padding: 4px 8px;
  font-size: 12px;
}
.helper-text {
  color: #6b7280;
  font-size: 13px;
}
.empty-card {
  text-align: center;
  color: #6b7280;
  padding: 40px 20px;
}

@media (max-width: 960px) {
  .kb-layout {
    grid-template-columns: 1fr;
  }
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
