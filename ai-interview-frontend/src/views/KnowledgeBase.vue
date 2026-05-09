<template>
  <div class="container">
    <div class="page-header">
      <div>
        <h1>岗位画像库</h1>
        <p class="page-subtitle">把任意目标岗位的核心能力、常见八股、典型任务、关键词和评分重点交给 AI 面试官，让技术岗与非技术岗训练都更贴近真实面试。</p>
      </div>
      <button class="btn-primary" @click="startCreate">
        {{ editingId ? '新建一份' : '+ 新建岗位画像' }}
      </button>
    </div>

    <div class="card intro-card">
      <h3>推荐填写方式</h3>
      <div class="intro-grid">
        <div>
          <strong>岗位画像内容</strong>
          <p>写岗位核心能力、典型任务、关键词、常见工作场景和入门岗位要求；技术岗可加入八股知识点。</p>
        </div>
        <div>
          <strong>重点测评方向</strong>
          <p>写你最想被重点核实的内容，比如项目深度、数据库、Redis、系统设计，或招聘流程、运营复盘、沟通协作。</p>
        </div>
        <div>
          <strong>额外面试官要求</strong>
          <p>写你希望面试官采用的风格，比如“多追问真实经历”“严格核验证据”“多给可执行建议”。</p>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <div class="card form-card">
        <h3>{{ editingId ? '编辑岗位画像' : '新建岗位画像' }}</h3>

        <div class="form-group">
          <label>画像标题</label>
          <input v-model="form.title" placeholder="例如：Python后端开发工程师岗位画像" />
        </div>

        <div class="form-group">
          <label>目标岗位</label>
          <input v-model="form.target_position" placeholder="例如：Python后端开发工程师" />
        </div>

        <div class="form-group">
          <label>岗位画像内容</label>
          <textarea
            v-model="form.knowledge_content"
            rows="10"
            placeholder="写该岗位的核心能力、典型任务、关键词、常见工作场景和能力要求"
          />
        </div>

        <div class="form-group">
          <label>重点测评方向</label>
          <textarea
            v-model="form.focus_points"
            rows="5"
            placeholder="例如：技术岗追问语言基础、数据库、Redis、HTTP、并发、系统设计；职能岗追问流程、数据、沟通和复盘"
          />
        </div>

        <div class="form-group">
          <label>额外面试官要求</label>
          <textarea
            v-model="form.interviewer_prompt"
            rows="4"
            placeholder="例如：回答模糊时继续追问证据；优先给出可执行的简历和面试改进建议"
          />
        </div>

        <label class="switch-row">
          <input v-model="form.is_active" type="checkbox" />
          <span>启用这份岗位画像</span>
        </label>

        <p v-if="formMsg" :class="formMsg.startsWith('✅') ? 'success-msg' : 'error'">{{ formMsg }}</p>

        <div class="form-actions">
          <button class="btn-primary" @click="handleSubmit" :disabled="saving">
            {{ saving ? '保存中...' : (editingId ? '保存修改' : '创建岗位画像') }}
          </button>
          <button v-if="editingId" class="btn-secondary" @click="resetForm">取消编辑</button>
        </div>
      </div>

      <div class="list-panel">
        <div class="list-header">
          <h3>可用岗位画像</h3>
          <input v-model="keyword" placeholder="按岗位 / 能力关键词筛选" />
        </div>

        <div v-if="loading" class="card empty-card">加载中...</div>

        <div v-else-if="filteredItems.length === 0" class="card empty-card">
          <p>还没有岗位画像。</p>
          <p class="muted">建议至少先整理一份目标岗位画像，这样 AI 面试官会更会问、更会评。</p>
        </div>

        <div v-else class="knowledge-list">
          <div v-for="item in filteredItems" :key="item.knowledge_base_id" class="card knowledge-item">
            <div class="item-head">
              <div>
                <h4>{{ item.title }}</h4>
                <p class="item-position">{{ item.target_position }}</p>
              </div>
              <div class="item-statuses">
                <span :class="['source-tag', item.scope === 'public' ? 'public' : 'private']">{{ item.source_label }}</span>
                <span :class="['status-tag', item.is_active ? 'active' : 'inactive']">
                  {{ item.is_active ? '启用中' : '已停用' }}
                </span>
                <span class="slice-tag" v-if="typeof item.slice_count === 'number'">切片 {{ item.slice_count }}</span>
              </div>
            </div>

            <p class="item-preview">{{ item.preview }}</p>

            <div v-if="item.focus_points" class="detail-block">
              <strong>训练重点：</strong>{{ item.focus_points }}
            </div>

            <div v-if="item.interviewer_prompt" class="detail-block">
              <strong>面试官要求：</strong>{{ item.interviewer_prompt }}
            </div>

            <div class="slice-debug-card">
              <div class="slice-debug-header">
                <div>
                  <strong>切片调试</strong>
                  <p class="slice-debug-text">
                    {{ typeof item.slice_count === 'number' ? `当前已生成 ${item.slice_count} 条切片` : '可按需展开查看切片预览' }}
                  </p>
                </div>
                <div class="slice-debug-actions">
                  <button class="btn-secondary action-btn" @click="toggleSlices(item)" :disabled="sliceState[item.knowledge_base_id]?.loading">
                    {{ sliceState[item.knowledge_base_id]?.open ? '收起切片' : '查看切片' }}
                  </button>
                  <button
                    v-if="item.editable"
                    class="btn-secondary action-btn"
                    @click="handleRebuildSlices(item)"
                    :disabled="sliceState[item.knowledge_base_id]?.rebuilding"
                  >
                    {{ sliceState[item.knowledge_base_id]?.rebuilding ? '重建中...' : '重建切片' }}
                  </button>
                </div>
              </div>

              <div v-if="sliceState[item.knowledge_base_id]?.open" class="slice-preview-wrap">
                <p v-if="sliceState[item.knowledge_base_id]?.loading" class="slice-loading">正在加载切片预览...</p>
                <p v-else-if="sliceState[item.knowledge_base_id]?.error" class="error">{{ sliceState[item.knowledge_base_id].error }}</p>
                <template v-else>
                  <div v-if="slicePreviewItems(item).length" class="slice-preview-list">
                    <div v-for="slice in slicePreviewItems(item)" :key="slice.id || slice.slice_id" class="slice-preview-item">
                      <div class="slice-preview-title">
                        <strong>{{ slice.title || `切片 #${slice.chunk_index || slice.sort_order || slice.slice_id || '-'}` }}</strong>
                        <span class="slice-preview-meta">{{ slice.slice_type || 'general' }}</span>
                      </div>
                      <p class="slice-preview-content">{{ slice.content }}</p>
                      <div class="slice-preview-tags">
                        <span v-for="tag in compactSliceTags(slice)" :key="`${slice.id || slice.slice_id}-${tag}`" class="slice-preview-tag">
                          {{ tag }}
                        </span>
                      </div>
                    </div>
                    <p v-if="hiddenSliceCount(item) > 0" class="slice-more-tip">
                      还有 {{ hiddenSliceCount(item) }} 条切片未展开，当前仅预览前 {{ slicePreviewLimit }} 条。
                    </p>
                  </div>
                  <p v-else class="slice-loading">当前还没有可用切片。</p>
                </template>
              </div>
            </div>

            <div class="item-footer">
              <span>更新于 {{ formatDate(item.updated_at || item.created_at) }}</span>
              <div v-if="item.editable" class="item-actions">
                <button class="btn-secondary action-btn" @click="handleEdit(item)">编辑</button>
                <button class="btn-danger action-btn" @click="handleDelete(item)">删除</button>
              </div>
              <span v-else class="public-tip">公共岗位画像由后台维护</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBases,
  getKnowledgeBaseSlices,
  rebuildKnowledgeBaseSlices,
  updateKnowledgeBase
} from '../api/knowledgeBase'

const loading = ref(true)
const saving = ref(false)
const keyword = ref('')
const items = ref([])
const editingId = ref(null)
const formMsg = ref('')
const sliceState = ref({})
const slicePreviewLimit = 4

const defaultForm = () => ({
  title: '',
  target_position: '',
  knowledge_content: '',
  focus_points: '',
  interviewer_prompt: '',
  is_active: true
})

const form = ref(defaultForm())

const filteredItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(item => {
    return [item.title, item.target_position, item.preview]
      .filter(Boolean)
      .some(text => text.toLowerCase().includes(kw))
  })
})

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function ensureSliceState(knowledgeBaseId) {
  if (!sliceState.value[knowledgeBaseId]) {
    sliceState.value[knowledgeBaseId] = {
      open: false,
      loading: false,
      rebuilding: false,
      items: [],
      total: 0,
      error: ''
    }
  }
  return sliceState.value[knowledgeBaseId]
}

function compactSliceTags(slice) {
  const groups = [
    ...(slice?.stage_tags || []).slice(0, 2),
    ...(slice?.role_tags || []).slice(0, 1),
    ...(slice?.topic_tags || []).slice(0, 2)
  ]
  return [...new Set(groups.filter(Boolean))].slice(0, 5)
}

function slicePreviewItems(item) {
  const state = sliceState.value[item.knowledge_base_id]
  return (state?.items || []).slice(0, slicePreviewLimit)
}

function hiddenSliceCount(item) {
  const state = sliceState.value[item.knowledge_base_id]
  const total = state?.total || state?.items?.length || 0
  return Math.max(total - slicePreviewLimit, 0)
}

async function loadSlices(item, force = false) {
  const state = ensureSliceState(item.knowledge_base_id)
  if (!force && state.items.length) return state

  state.loading = true
  state.error = ''
  try {
    const data = await getKnowledgeBaseSlices(item.knowledge_base_id)
    state.items = data.items || []
    state.total = data.total || state.items.length
  } catch (e) {
    state.error = e.message
  } finally {
    state.loading = false
  }
  return state
}

async function toggleSlices(item) {
  const state = ensureSliceState(item.knowledge_base_id)
  state.open = !state.open
  if (state.open) {
    await loadSlices(item)
  }
}

async function handleRebuildSlices(item) {
  const state = ensureSliceState(item.knowledge_base_id)
  state.rebuilding = true
  state.error = ''
  try {
    const data = await rebuildKnowledgeBaseSlices(item.knowledge_base_id)
    state.items = data.items || []
    state.total = data.total || state.items.length
    state.open = true
    item.slice_count = state.total
  } catch (e) {
    state.error = e.message
  } finally {
    state.rebuilding = false
  }
}

async function loadItems() {
  loading.value = true
  try {
    const data = await getKnowledgeBases()
    items.value = data.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function startCreate() {
  resetForm()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function resetForm() {
  editingId.value = null
  form.value = defaultForm()
  formMsg.value = ''
}

function handleEdit(item) {
  if (!item.editable) return
  editingId.value = item.knowledge_base_id
  form.value = {
    title: item.title || '',
    target_position: item.target_position || '',
    knowledge_content: item.knowledge_content || '',
    focus_points: item.focus_points || '',
    interviewer_prompt: item.interviewer_prompt || '',
    is_active: !!item.is_active
  }
  formMsg.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function handleSubmit() {
  formMsg.value = ''
  if (!form.value.title.trim() || !form.value.target_position.trim() || !form.value.knowledge_content.trim()) {
    formMsg.value = '标题、目标岗位和画像内容不能为空'
    return
  }

  saving.value = true
  try {
    const payload = {
      ...form.value,
      title: form.value.title.trim(),
      target_position: form.value.target_position.trim(),
      knowledge_content: form.value.knowledge_content.trim(),
      focus_points: form.value.focus_points.trim(),
      interviewer_prompt: form.value.interviewer_prompt.trim()
    }

    if (editingId.value) {
      await updateKnowledgeBase(editingId.value, payload)
      await loadItems()
      formMsg.value = '✅ 岗位画像已更新'
    } else {
      await createKnowledgeBase(payload)
      await loadItems()
      resetForm()
      formMsg.value = '✅ 岗位画像已创建'
    }
  } catch (e) {
    formMsg.value = e.message
  } finally {
    saving.value = false
  }
}

async function handleDelete(item) {
  if (!item.editable) return
  if (!confirm(`确定删除“${item.title}”吗？删除后已完成面试的快照不会受影响。`)) return
  try {
    await deleteKnowledgeBase(item.knowledge_base_id)
    if (editingId.value === item.knowledge_base_id) {
      resetForm()
    }
    await loadItems()
  } catch (e) {
    alert('删除失败：' + e.message)
  }
}

onMounted(loadItems)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: 20px 0 16px;
}
.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}
.page-subtitle {
  color: #6b7280;
  line-height: 1.7;
  max-width: 720px;
}
.intro-card {
  margin-bottom: 16px;
}
.intro-card h3 {
  margin-bottom: 14px;
}
.intro-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.intro-grid p {
  color: #6b7280;
  line-height: 1.7;
  margin-top: 8px;
  font-size: 14px;
}
.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 420px) minmax(0, 1fr);
  gap: 16px;
}
.form-card h3,
.list-header h3 {
  margin-bottom: 16px;
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
.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  margin: 6px 0 16px;
}
.switch-row input {
  width: auto;
}
.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.knowledge-item {
  padding: 20px;
}
.item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.item-statuses {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-head h4 {
  font-size: 18px;
  margin-bottom: 6px;
}
.item-position {
  color: #6b7280;
  font-size: 14px;
}
.source-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}
.source-tag.private {
  background: #ede9fe;
  color: #5b21b6;
}
.source-tag.public {
  background: #dbeafe;
  color: #1d4ed8;
}
.slice-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  background: #eef2ff;
  color: #4338ca;
}
.status-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}
.status-tag.active {
  background: #dcfce7;
  color: #166534;
}
.status-tag.inactive {
  background: #e5e7eb;
  color: #4b5563;
}
.item-preview {
  margin: 14px 0;
  line-height: 1.8;
  color: #374151;
}
.detail-block {
  margin-top: 10px;
  color: #4b5563;
  line-height: 1.7;
  font-size: 14px;
}
.slice-debug-card {
  margin-top: 14px;
  padding: 14px;
  border-radius: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}
.slice-debug-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.slice-debug-text {
  margin-top: 6px;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}
.slice-debug-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.slice-preview-wrap {
  margin-top: 14px;
}
.slice-preview-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.slice-preview-item {
  padding: 12px;
  border-radius: 10px;
  background: white;
  border: 1px solid #e5e7eb;
}
.slice-preview-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.slice-preview-meta {
  flex-shrink: 0;
  font-size: 12px;
  color: #6366f1;
}
.slice-preview-content {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}
.slice-preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.slice-preview-tag {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: #eef2ff;
  color: #4338ca;
}
.slice-loading,
.slice-more-tip {
  font-size: 13px;
  color: #6b7280;
}
.slice-more-tip {
  margin-top: 6px;
}
.item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
  color: #6b7280;
  font-size: 13px;
}
.item-actions {
  display: flex;
  gap: 8px;
}
.public-tip {
  color: #6b7280;
  font-size: 13px;
}
.action-btn {
  padding: 6px 14px;
  font-size: 13px;
}
.empty-card {
  text-align: center;
  color: #6b7280;
  padding: 40px 20px;
}
.muted {
  font-size: 14px;
  margin-top: 8px;
}
.error {
  color: #ef4444;
  font-size: 13px;
}
.success-msg {
  color: #059669;
  font-size: 13px;
}
.btn-danger {
  background: #ef4444;
  color: white;
}
.btn-danger:hover {
  background: #dc2626;
}

@media (max-width: 900px) {
  .intro-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
