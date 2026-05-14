<template>
  <div>
    <div class="page-head">
      <div>
        <h1>面试经验管理</h1>
        <p>
          按岗位集中查看公共岗位画像中的结构化问答经验。这里不新建独立数据表，保存与编辑仍回到对应岗位画像的“问答经验”分区。
        </p>
      </div>
      <router-link class="btn-primary" to="/knowledge-bases">编辑岗位画像</router-link>
    </div>

    <div class="summary-grid">
      <div class="card summary-card">
        <span>岗位画像</span>
        <strong>{{ stats.profileCount }}</strong>
      </div>
      <div class="card summary-card">
        <span>问答经验</span>
        <strong>{{ stats.experienceCount }}</strong>
      </div>
      <div class="card summary-card">
        <span>可入库</span>
        <strong>{{ stats.approvedCount }}</strong>
      </div>
      <div class="card summary-card">
        <span>待核验</span>
        <strong>{{ stats.pendingCount }}</strong>
      </div>
    </div>

    <div class="card filters">
      <input v-model="keyword" placeholder="搜索岗位、问题、能力、来源" />
      <select v-model="positionFilter">
        <option value="">全部岗位</option>
        <option v-for="position in positions" :key="position" :value="position">{{ position }}</option>
      </select>
      <select v-model="auditFilter">
        <option value="">全部审核状态</option>
        <option v-for="status in interviewAuditStatuses" :key="status" :value="status">{{ status }}</option>
      </select>
    </div>

    <div v-if="loading" class="card empty-card">加载中...</div>
    <div v-else-if="filteredExperiences.length === 0" class="card empty-card">
      暂无可展示的结构化问答经验。请先在公共岗位画像的“问答经验”分区录入面经卡片。
    </div>

    <div v-else class="experience-list">
      <article v-for="item in filteredExperiences" :key="item.key" class="card experience-card">
        <div class="experience-head">
          <div>
            <h3>{{ item.question || '未命名问题' }}</h3>
            <p>{{ item.target_position }} / {{ item.profile_title }}</p>
          </div>
          <span :class="['audit-badge', auditClass(item.audit_status)]">{{ item.audit_status }}</span>
        </div>

        <div class="meta-row">
          <span>考察能力：{{ item.ability || '待补' }}</span>
          <span>难度：{{ item.difficulty || '待补' }}</span>
          <span>场景：{{ item.company_context || '待补' }}</span>
        </div>

        <section>
          <h4>参考回答要点</h4>
          <p>{{ item.answer_points || '待补充参考回答要点。' }}</p>
        </section>
        <section>
          <h4>复盘反思</h4>
          <p>{{ item.reflection || '待补充复盘反思。' }}</p>
        </section>
        <section>
          <h4>来源说明</h4>
          <p>{{ item.source || '待补充来源说明。' }}</p>
        </section>

        <div class="card-actions">
          <button class="btn-sm" @click="openProfile(item.knowledge_base_id)">回到岗位画像编辑</button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { knowledgeBaseApi } from '../api'
import {
  interviewAuditStatuses,
  parseInterviewExperienceMarkdown
} from '../utils/interviewExperience'

const router = useRouter()
const loading = ref(true)
const items = ref([])
const keyword = ref('')
const positionFilter = ref('')
const auditFilter = ref('')

const sectionHeadingMap = {
  岗位要求: 'job_requirements',
  问答经验: 'interview_experience',
  真实面试经验: 'interview_experience',
  面试经验: 'interview_experience',
  能力模型: 'ability_model',
  面试追问: 'followup_rules',
  其他内容: 'legacy_content'
}

function parseKnowledgeSections(text) {
  const content = String(text || '')
  const result = {
    interview_experience: ''
  }
  const matches = [...content.matchAll(/^#{1,4}\s*(岗位要求|问答经验|真实面试经验|面试经验|能力模型|面试追问|其他内容)\s*$/gm)]
  if (!matches.length) return result

  matches.forEach((match, index) => {
    const start = match.index + match[0].length
    const end = matches[index + 1]?.index ?? content.length
    const key = sectionHeadingMap[match[1]]
    if (key === 'interview_experience') {
      result.interview_experience = [result.interview_experience, content.slice(start, end).trim()]
        .filter(Boolean)
        .join('\n\n')
    }
  })
  return result
}

const experiences = computed(() => {
  const rows = []
  items.value.forEach(profile => {
    const content = parseKnowledgeSections(profile.knowledge_content).interview_experience
    const parsed = parseInterviewExperienceMarkdown(content)
    parsed.items.forEach((experience, index) => {
      rows.push({
        ...experience,
        key: `${profile.knowledge_base_id}-${index}`,
        knowledge_base_id: profile.knowledge_base_id,
        profile_title: profile.title,
        target_position: profile.target_position
      })
    })
  })
  return rows
})

const positions = computed(() => {
  return [...new Set(items.value.map(item => item.target_position).filter(Boolean))].sort()
})

const filteredExperiences = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return experiences.value.filter(item => {
    if (positionFilter.value && item.target_position !== positionFilter.value) return false
    if (auditFilter.value && item.audit_status !== auditFilter.value) return false
    if (!kw) return true
    return [
      item.question,
      item.answer_points,
      item.reflection,
      item.company_context,
      item.ability,
      item.source,
      item.target_position,
      item.profile_title
    ].filter(Boolean).some(value => String(value).toLowerCase().includes(kw))
  })
})

const stats = computed(() => {
  return {
    profileCount: items.value.length,
    experienceCount: experiences.value.length,
    approvedCount: experiences.value.filter(item => item.audit_status === '可入库').length,
    pendingCount: experiences.value.filter(item => item.audit_status === '待核验').length
  }
})

function auditClass(status) {
  return {
    可入库: 'audit-ok',
    仅参考: 'audit-info',
    不采用: 'audit-bad',
    待核验: 'audit-warn'
  }[status] || 'audit-warn'
}

function openProfile(id) {
  router.push({ path: '/knowledge-bases', query: { id } })
}

async function loadItems() {
  loading.value = true
  try {
    const data = await knowledgeBaseApi.list()
    items.value = data.items || []
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

onMounted(loadItems)
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.page-head h1 {
  font-size: 20px;
  margin-bottom: 8px;
}
.page-head p {
  max-width: 760px;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.7;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
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
.filters {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 220px 180px;
  gap: 12px;
  margin-bottom: 16px;
}
.experience-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
}
.experience-card {
  padding: 18px;
}
.experience-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.experience-head h3 {
  font-size: 16px;
  margin-bottom: 6px;
  color: #111827;
}
.experience-head p,
.meta-row,
.experience-card section p {
  color: #4b5563;
  font-size: 13px;
  line-height: 1.65;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.meta-row span {
  padding: 4px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f9fafb;
}
.experience-card section {
  margin-top: 10px;
}
.experience-card h4 {
  font-size: 13px;
  margin-bottom: 4px;
  color: #111827;
}
.audit-badge {
  flex: 0 0 auto;
  height: 24px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid #d1d5db;
}
.audit-ok {
  background: #ecfdf5;
  color: #047857;
  border-color: #a7f3d0;
}
.audit-info {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #bfdbfe;
}
.audit-warn {
  background: #fffbeb;
  color: #92400e;
  border-color: #fde68a;
}
.audit-bad {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}
.card-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.empty-card {
  padding: 28px;
  text-align: center;
  color: #6b7280;
}
@media (max-width: 900px) {
  .summary-grid,
  .filters,
  .experience-list {
    grid-template-columns: 1fr;
  }
  .page-head {
    flex-direction: column;
  }
}
</style>
