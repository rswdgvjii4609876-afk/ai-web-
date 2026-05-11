<template>
  <div class="container">
    <div class="tasks-hero card">
      <div>
        <p class="eyebrow">学习任务</p>
        <h1>把能力差距变成账号里的长期学习清单</h1>
        <p>
          报告和能力诊断中加入的短板会同步到服务器。换浏览器、换设备或清缓存后，
          学习任务、完成状态、学习笔记和薄弱项变化仍会保留。
        </p>
      </div>
      <div class="hero-actions">
        <router-link to="/training-review" class="btn-secondary hero-btn">训练复盘</router-link>
        <router-link to="/ability-diagnosis" class="btn-secondary hero-btn">能力诊断</router-link>
        <router-link to="/resume/upload" class="btn-primary hero-btn primary">新建面试</router-link>
      </div>
    </div>

    <div v-if="legacyCount" class="migration-card card">
      <div>
        <strong>检测到旧版本地学习任务</strong>
        <p>浏览器里还有 {{ legacyCount }} 项旧任务，可以一键迁移到当前账号。迁移后本地备份不会自动删除。</p>
      </div>
      <button class="btn-primary" type="button" :disabled="isMigrating" @click="migrateLegacyTasks">
        {{ isMigrating ? '迁移中...' : '迁移到账号' }}
      </button>
    </div>

    <div class="plan-generator card">
      <div class="generator-head">
        <div>
          <p class="eyebrow">生成学习计划</p>
          <h2>把缺失能力生成可编辑任务</h2>
          <p>
            可以选择 AI 根据后台基础路线生成，也可以直接使用后台维护的成熟计划。补充资料只适合放链接、摘要和小段文本，不要上传大型文件。
          </p>
        </div>
        <button class="btn-secondary" type="button" :disabled="planOptionsLoading" @click="loadPlanOptions">
          {{ planOptionsLoading ? '读取中...' : '刷新路线选项' }}
        </button>
      </div>

      <div class="generator-grid">
        <label>
          目标岗位
          <input v-model="planForm.target_position" placeholder="例如：Python后端开发工程师 / 产品助理" />
        </label>
        <label>
          生成方式
          <select v-model="planForm.mode">
            <option value="ai_generate">AI 生成初步计划</option>
            <option value="mature_plan">使用后台成熟计划</option>
          </select>
        </label>
        <label>
          缺失能力
          <textarea
            v-model="planForm.abilities_text"
            rows="4"
            placeholder="每行一个能力，例如：FastAPI 接口设计&#10;SQL 查询与事务&#10;项目复盘表达"
          ></textarea>
        </label>
        <label>
          补充轻量资料
          <textarea
            v-model="planForm.supplemental_materials"
            rows="4"
            placeholder="可填链接、学习资料摘要、小段文本。不要粘贴大型文件全文。"
          ></textarea>
        </label>
      </div>

      <div class="generator-actions">
        <label class="switch-inline">
          <input v-model="planForm.allow_web_search" type="checkbox" />
          <span>允许使用 OpenAI 联网搜索补充资料来源</span>
        </label>
        <button class="btn-primary" type="button" :disabled="generatingPlan" @click="handleGeneratePlan">
          {{ generatingPlan ? '生成中...' : '生成学习计划草稿' }}
        </button>
        <button class="btn-secondary" type="button" :disabled="!draftTasks.length || savingDraft" @click="saveDraftTasks">
          {{ savingDraft ? '保存中...' : '保存草稿到学习任务' }}
        </button>
      </div>

      <div v-if="planOptions.templates?.length || planOptions.mature_plans?.length" class="generator-meta">
        <span>基础模板 {{ planOptions.templates?.length || 0 }}</span>
        <span>成熟计划 {{ planOptions.mature_plans?.length || 0 }}</span>
        <span>{{ planOptions.web_search_available ? 'OpenAI 联网可用' : '未检测到 OpenAI Key，联网不可用' }}</span>
      </div>

      <div v-if="draftTasks.length" class="draft-list">
        <article v-for="(task, index) in draftTasks" :key="`${task.task_id || task.title}-${index}`" class="draft-item">
          <div class="draft-head">
            <strong>任务 {{ index + 1 }}</strong>
            <button type="button" class="remove-btn" @click="draftTasks.splice(index, 1)">移除</button>
          </div>
          <label>任务标题<input v-model="task.title" /></label>
          <label>学习材料<textarea v-model="task.learning_material" rows="3"></textarea></label>
          <label>练习任务<textarea v-model="task.practice_task" rows="3"></textarea></label>
          <div class="draft-grid">
            <label>预计耗时（分钟）<input v-model.number="task.estimated_minutes" type="number" min="1" /></label>
            <label>截止日期<input v-model="task.due_date" type="date" /></label>
          </div>
          <label>验收方式<textarea v-model="task.acceptanceText" rows="3" placeholder="每行一条验收标准"></textarea></label>
          <label>备注<textarea v-model="task.note" rows="2"></textarea></label>
        </article>
      </div>
    </div>

    <div class="task-toolbar card">
      <div>
        <h2>任务库</h2>
        <p v-if="loading">正在读取服务器学习任务...</p>
        <p v-else>{{ pendingCount }} 项待完成，{{ doneCount }} 项已完成</p>
      </div>
      <div class="toolbar-actions">
        <button class="btn-secondary" type="button" @click="loadTasks" :disabled="loading">刷新</button>
        <button class="btn-secondary" type="button" @click="downloadTasks" :disabled="!tasks.length">
          下载进度 JSON
        </button>
        <button class="btn-secondary" type="button" @click="triggerImport">
          上传进度 JSON
        </button>
        <button class="btn-secondary danger-outline" type="button" @click="clearTasks" :disabled="!tasks.length">
          清空账号任务
        </button>
        <input ref="fileInput" class="hidden-input" type="file" accept="application/json,.json" @change="handleImport" />
      </div>
    </div>

    <div v-if="tasks.length" class="progress-grid">
      <div class="card progress-card">
        <span>总任务</span>
        <strong>{{ tasks.length }}</strong>
      </div>
      <div class="card progress-card">
        <span>完成率</span>
        <strong>{{ completionRate }}%</strong>
      </div>
      <div class="card progress-card">
        <span>路线阶段</span>
        <strong>{{ routeStageCount }}</strong>
      </div>
      <div class="card progress-card">
        <span>预计剩余</span>
        <strong>{{ remainingHoursText }}</strong>
      </div>
    </div>

    <div v-if="tasks.length" class="filter-card card">
      <label>
        路线阶段
        <select v-model="stageFilter">
          <option value="">全部阶段</option>
          <option v-for="stage in routeStageOptions" :key="stage" :value="stage">{{ stageLabel(stage) }}</option>
        </select>
      </label>
      <label>
        能力项
        <select v-model="abilityFilter">
          <option value="">全部能力</option>
          <option v-for="ability in abilityOptions" :key="ability" :value="ability">{{ ability }}</option>
        </select>
      </label>
      <label>
        完成状态
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option value="pending">待完成</option>
          <option value="done">已完成</option>
        </select>
      </label>
    </div>

    <p v-if="message" :class="messageType === 'error' ? 'message error' : 'message success'">
      {{ message }}
    </p>

    <div v-if="!loading && !tasks.length" class="card empty-card">
      <h2>还没有学习任务</h2>
      <p>先上传简历生成分析，或在能力诊断、面试报告中把能力短板加入学习任务。</p>
      <div class="empty-actions">
        <router-link to="/resume/upload" class="btn-primary empty-action">上传简历</router-link>
        <router-link to="/ability-diagnosis" class="btn-secondary empty-action">查看能力诊断</router-link>
        <router-link to="/training-review" class="btn-secondary empty-action">训练复盘</router-link>
      </div>
    </div>

    <div v-else-if="tasks.length && !filteredTasks.length" class="card empty-card">
      <h2>当前筛选下没有任务</h2>
      <p>换一个路线阶段、能力项或完成状态再看。</p>
    </div>

    <div v-else class="task-list">
      <article v-for="task in filteredTasks" :key="task.task_id" class="card task-card">
        <div class="task-head">
          <label class="task-check">
            <input type="checkbox" :checked="task.done" @change="updateTask(task.task_id, { done: $event.target.checked })" />
            <span :class="{ done: task.done }">{{ task.title }}</span>
          </label>
          <button class="remove-btn" type="button" @click="removeTask(task.task_id)">移除</button>
        </div>

        <div class="task-meta">
          <span>{{ task.target_position || '未指定岗位' }}</span>
          <span>{{ task.ability_name || '能力项' }}</span>
          <span v-if="task.priority_score !== ''">优先级 {{ task.priority_score }}</span>
          <span>来源：{{ sourceLabel(task.source_type) }}</span>
          <span v-if="task.route_stage">阶段：{{ stageLabel(task.route_stage) }}</span>
          <span v-if="task.task_type">类型：{{ taskTypeLabel(task.task_type) }}</span>
          <span v-if="task.estimated_minutes">预计 {{ minutesText(task.estimated_minutes) }}</span>
        </div>

        <div class="task-detail">
          <div>
            <strong>学习材料</strong>
            <p>{{ task.learning_material || '岗位画像知识库与学习路线' }}</p>
            <p v-if="task.route_source" class="route-source">路线来源：{{ routeSourceLabel(task.route_source) }}</p>
          </div>
          <div>
            <strong>练习任务</strong>
            <p>{{ task.practice_task || '完成一次可展示练习，并写下复盘。' }}</p>
          </div>
          <div>
            <strong>验收方式</strong>
            <ul>
              <li v-for="criterion in criteriaList(task)" :key="criterion">{{ criterion }}</li>
            </ul>
          </div>
          <div v-if="task.evidence_basis">
            <strong>来源依据</strong>
            <p>{{ task.evidence_basis }}</p>
          </div>
        </div>

        <div class="task-notes">
          <label>
            学习笔记
            <textarea
              :value="task.note"
              placeholder="记录学了什么、哪里还不熟、下一步怎么练。"
              @change="updateTask(task.task_id, { note: $event.target.value })"
            ></textarea>
          </label>
          <label>
            薄弱项变化
            <textarea
              :value="task.weak_change"
              placeholder="例如：已完成 FastAPI 路由练习，但数据库事务还需要复习。"
              @change="updateTask(task.task_id, { weak_change: $event.target.value })"
            ></textarea>
          </label>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { generateLearningPlan, getLearningPlanOptions } from '../api/learningPlans'
import {
  LEARNING_TASKS_VERSION,
  loadLearningTasksFromServer,
  migrateLocalLearningTasksToServer,
  readLearningTaskStore,
  removeLearningTaskFromServer,
  updateLearningTaskOnServer,
  upsertLearningTasksToServer,
  validateLearningTaskPayload
} from '../utils/learningTasks'

const tasks = ref([])
const fileInput = ref(null)
const message = ref('')
const messageType = ref('success')
const loading = ref(false)
const isMigrating = ref(false)
const legacyCount = ref(0)
const stageFilter = ref('')
const abilityFilter = ref('')
const statusFilter = ref('')
const planOptionsLoading = ref(false)
const generatingPlan = ref(false)
const savingDraft = ref(false)
const planOptions = ref({ templates: [], mature_plans: [], ability_options: [] })
const planForm = ref({
  target_position: '',
  mode: 'ai_generate',
  abilities_text: '',
  supplemental_materials: '',
  allow_web_search: false
})
const draftTasks = ref([])

const doneCount = computed(() => tasks.value.filter(task => task.done).length)
const pendingCount = computed(() => tasks.value.length - doneCount.value)
const completionRate = computed(() => {
  if (!tasks.value.length) return 0
  return Math.round((doneCount.value / tasks.value.length) * 100)
})
const routeStageOptions = computed(() => uniqueValues(tasks.value.map(task => task.route_stage)))
const abilityOptions = computed(() => uniqueValues(tasks.value.map(task => task.ability_name)))
const routeStageCount = computed(() => routeStageOptions.value.length)
const remainingMinutes = computed(() => tasks.value
  .filter(task => !task.done)
  .reduce((sum, task) => sum + (Number(task.estimated_minutes) || 0), 0))
const remainingHoursText = computed(() => {
  if (!remainingMinutes.value) return '-'
  const hours = Math.round((remainingMinutes.value / 60) * 10) / 10
  return `${hours}h`
})
const filteredTasks = computed(() => tasks.value.filter((task) => {
  if (stageFilter.value && task.route_stage !== stageFilter.value) return false
  if (abilityFilter.value && task.ability_name !== abilityFilter.value) return false
  if (statusFilter.value === 'done' && !task.done) return false
  if (statusFilter.value === 'pending' && task.done) return false
  return true
}))

onMounted(() => {
  refreshLegacyCount()
  loadTasks()
  loadPlanOptions()
})

async function loadTasks() {
  loading.value = true
  try {
    const store = await loadLearningTasksFromServer()
    tasks.value = store.tasks
    if (!tasks.value.length) setMessage('', 'success')
  } catch (e) {
    setMessage(e.message || '服务器学习任务读取失败，请确认登录状态。', 'error')
  } finally {
    loading.value = false
  }
}

async function loadPlanOptions() {
  planOptionsLoading.value = true
  try {
    const options = await getLearningPlanOptions({
      target_position: planForm.value.target_position || undefined
    })
    planOptions.value = options || { templates: [], mature_plans: [], ability_options: [] }
    if (!planForm.value.target_position && options?.target_position) {
      planForm.value.target_position = options.target_position
    }
    if (!planForm.value.abilities_text && Array.isArray(options?.ability_options) && options.ability_options.length) {
      planForm.value.abilities_text = options.ability_options
        .slice(0, 5)
        .map(item => item.ability_name || item.name || item.title)
        .filter(Boolean)
        .join('\n')
    }
  } catch (e) {
    setMessage(e.message || '学习路线选项读取失败，请确认数据库迁移是否完成。', 'error')
  } finally {
    planOptionsLoading.value = false
  }
}

function planAbilities() {
  return String(planForm.value.abilities_text || '')
    .split(/\r?\n|,|，/)
    .map(item => item.trim())
    .filter(Boolean)
    .map((name, index) => ({ ability_id: `manual_${index + 1}`, name, missing_keywords: [name] }))
}

function normalizeDraftTask(task, index) {
  const criteria = Array.isArray(task.acceptance_criteria)
    ? task.acceptance_criteria
    : String(task.acceptance_criteria || task.deliverable || '')
      .split(/\r?\n/)
      .map(item => item.trim())
      .filter(Boolean)
  return {
    ...task,
    task_key: task.task_key || task.task_id || `generated_plan_${Date.now()}_${index}`,
    task_id: task.task_id || task.task_key || `generated_plan_${Date.now()}_${index}`,
    title: task.title || `补强${task.ability_name || '岗位能力'}`,
    target_position: task.target_position || planForm.value.target_position,
    source_type: task.source_type || 'generated_learning_plan',
    learning_material: task.learning_material || task.material || '',
    practice_task: task.practice_task || task.practice || '',
    estimated_minutes: Number(task.estimated_minutes) || 120,
    acceptance_criteria: criteria,
    acceptanceText: criteria.join('\n'),
    note: task.note || ''
  }
}

async function handleGeneratePlan() {
  const abilities = planAbilities()
  if (!planForm.value.target_position.trim()) {
    setMessage('请先填写目标岗位。', 'error')
    return
  }
  if (!abilities.length) {
    setMessage('请至少填写 1 个缺失能力。', 'error')
    return
  }
  generatingPlan.value = true
  try {
    const plan = await generateLearningPlan({
      target_position: planForm.value.target_position.trim(),
      abilities,
      mode: planForm.value.mode,
      allow_web_search: planForm.value.allow_web_search,
      supplemental_materials: planForm.value.supplemental_materials
    })
    draftTasks.value = (plan.tasks || []).map(normalizeDraftTask)
    const searchNote = plan.web_search_status === 'used' ? '，已使用联网搜索补充来源' : ''
    setMessage(`已生成 ${draftTasks.value.length} 个学习任务草稿${searchNote}。请检查后保存。`)
  } catch (e) {
    setMessage(e.message || '学习计划生成失败，请稍后重试。', 'error')
  } finally {
    generatingPlan.value = false
  }
}

async function saveDraftTasks() {
  if (!draftTasks.value.length) return
  savingDraft.value = true
  try {
    const payload = draftTasks.value.map(task => ({
      ...task,
      acceptance_criteria: String(task.acceptanceText || '')
        .split(/\r?\n/)
        .map(item => item.trim())
        .filter(Boolean),
      task_metadata: {
        ...(task.task_metadata || {}),
        saved_from: 'learning_plan_generator'
      }
    }))
    await upsertLearningTasksToServer(payload, { replaceProgress: false })
    draftTasks.value = []
    await loadTasks()
    setMessage('学习计划草稿已保存到账号学习任务。')
  } catch (e) {
    setMessage(e.message || '学习计划保存失败。', 'error')
  } finally {
    savingDraft.value = false
  }
}

function refreshLegacyCount() {
  legacyCount.value = readLearningTaskStore().tasks.length
}

async function migrateLegacyTasks() {
  isMigrating.value = true
  try {
    const result = await migrateLocalLearningTasksToServer()
    await loadTasks()
    setMessage(`已迁移 ${result.migrated || 0} 项学习任务到账号。`)
  } catch (e) {
    setMessage(e.message || '旧版本地任务迁移失败。', 'error')
  } finally {
    isMigrating.value = false
    refreshLegacyCount()
  }
}

async function updateTask(taskId, patch) {
  try {
    const updated = await updateLearningTaskOnServer(taskId, patch)
    tasks.value = tasks.value.map(task => (task.task_id === taskId ? { ...task, ...updated } : task))
    setMessage('学习任务已同步。')
  } catch (e) {
    setMessage(e.message || '学习任务同步失败。', 'error')
  }
}

async function removeTask(taskId) {
  try {
    await removeLearningTaskFromServer(taskId)
    tasks.value = tasks.value.filter(task => task.task_id !== taskId)
    setMessage('学习任务已移除。')
  } catch (e) {
    setMessage(e.message || '学习任务移除失败。', 'error')
  }
}

async function clearTasks() {
  if (!confirm('确定清空当前账号的学习任务吗？清空前建议先下载 JSON 备份。')) return
  try {
    await Promise.all(tasks.value.map(task => removeLearningTaskFromServer(task.task_id)))
    tasks.value = []
    setMessage('账号学习任务已清空。')
  } catch (e) {
    setMessage(e.message || '清空学习任务失败。', 'error')
  }
}

function criteriaList(task) {
  if (Array.isArray(task.acceptance_criteria) && task.acceptance_criteria.length) return task.acceptance_criteria
  return ['完成对应练习或资料整理', '写下复盘笔记', '再次模拟面试验证表达']
}

function sourceLabel(type) {
  return {
    ability_gap: '能力差距',
    learning_plan: '学习计划',
    report_training: '报告建议',
    report_weakness: '报告短板',
    diagnosis_fallback: '诊断兜底'
  }[type] || '学习任务'
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'))
}

function stageLabel(stage) {
  return {
    python_basic: 'Python 基础',
    web_api_foundation: 'Web/API 基础',
    database_orm: '数据库与 ORM',
    fastapi_framework: 'FastAPI 框架',
    middleware_engineering: '中间件与工程化',
    project_review: '项目复盘',
    java_foundation: 'Java 基础',
    spring_boot_api: 'Spring Boot 接口',
    java_database_cache: '数据库与缓存',
    jvm_concurrency_ops: 'JVM/并发/排障',
    frontend_language_foundation: 'JS/TS 基础',
    frontend_framework_component: '前端框架与组件',
    frontend_engineering: '前端工程化',
    frontend_performance_review: '性能优化复盘',
    qa_case_design: '测试用例设计',
    qa_api_sql: '接口测试与 SQL',
    qa_automation: '自动化与回归',
    qa_bug_review: '缺陷定位复盘',
    ml_foundation: '机器学习基础',
    data_feature_engineering: '数据与特征工程',
    deep_learning_embedding: '深度学习与向量',
    experiment_deployment_review: '实验与上线风险',
    data_sql_processing: 'SQL 与数据处理',
    metric_system: '业务指标体系',
    visualization_report: '可视化报告',
    business_diagnosis: '业务归因',
    product_requirement_analysis: '产品需求分析',
    prd_prototype: 'PRD 与原型',
    product_metric_review: '产品指标复盘',
    product_collaboration: '产品协作推进',
    operation_execution: '运营执行',
    user_feedback: '用户反馈',
    operation_data_review: '运营数据复盘',
    operation_growth_plan: '增长实验',
    content_planning: '内容选题',
    copywriting_output: '文案产出',
    media_data_review: '内容数据复盘',
    account_iteration: '账号迭代策略',
    hr_recruitment_process: '招聘流程',
    hr_communication: 'HR 沟通',
    hr_labor_compliance: '劳动合规',
    hr_data_office: 'HR 数据记录',
    recruiting_channel: '招聘渠道',
    resume_screening: '简历筛选',
    interview_invitation: '面试邀约',
    recruiting_data_record: '招聘数据复盘',
    admin_office_tools: '办公文档',
    admin_process_execution: '行政流程执行',
    admin_meeting_event: '会议活动支持',
    admin_service_compliance: '服务与合规',
    tech_foundation: '技术基础',
    tech_project_practice: '技术项目练习',
    tech_debug_review: '问题定位复盘',
    tech_interview_expression: '技术面试表达',
    functional_process: '流程执行',
    functional_communication: '沟通协作',
    functional_document: '文档与数据',
    functional_review: '结果复盘',
    general_position_improvement: '通用岗位提升'
  }[stage] || stage
}

function taskTypeLabel(type) {
  return {
    theory_demo: '理论 + Demo',
    demo_practice: 'Demo 练习',
    project_practice: '项目练习',
    project_review: '项目复盘',
    case_practice: '案例练习',
    document_output: '文档产出',
    scenario_practice: '情景演练',
    theory_case: '理论 + 场景',
    general_practice: '通用练习'
  }[type] || type
}

function routeSourceLabel(source) {
  return {
    project_builtin_python_backend_route: '内置 Python 后端学习路线',
    project_builtin_python_basic_route: '内置 Python 基础学习路线',
    project_builtin_java_backend_route: '内置 Java 后端学习路线',
    project_builtin_frontend_route: '内置前端开发学习路线',
    project_builtin_qa_route: '内置测试工程师学习路线',
    project_builtin_algorithm_route: '内置算法工程师学习路线',
    project_builtin_data_analyst_route: '内置数据分析学习路线',
    project_builtin_product_position_route: '岗位画像产品能力路线',
    project_builtin_operations_route: '岗位画像运营能力路线',
    project_builtin_new_media_route: '岗位画像新媒体路线',
    project_builtin_hr_route: '岗位画像 HR 能力路线',
    project_builtin_recruiting_route: '岗位画像招聘能力路线',
    project_builtin_admin_route: '岗位画像行政能力路线',
    project_builtin_tech_general_route: '岗位画像技术通用路线',
    project_builtin_functional_general_route: '岗位画像职能通用路线',
    project_builtin_general_position_route: '岗位画像通用路线'
  }[source] || source
}

function minutesText(value) {
  const minutes = Number(value) || 0
  if (!minutes) return '-'
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.round((minutes / 60) * 10) / 10
  return `${hours} 小时`
}

function downloadTasks() {
  const payload = {
    version: LEARNING_TASKS_VERSION,
    tasks: tasks.value,
    exported_at: new Date().toISOString()
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `职启智评学习任务_${Date.now()}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  setMessage('学习任务 JSON 已下载。')
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleImport(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    const payload = JSON.parse(await file.text())
    if (!validateLearningTaskPayload(payload)) {
      setMessage('上传失败：JSON 结构不符合 learning_tasks_v1。', 'error')
      return
    }
    await upsertLearningTasksToServer(payload.tasks, { replaceProgress: true })
    await loadTasks()
    setMessage('学习任务已导入当前账号。')
  } catch {
    setMessage('上传失败：无法解析或写入这个 JSON 文件。', 'error')
  } finally {
    event.target.value = ''
  }
}

function setMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
}
</script>

<style scoped>
.tasks-hero {
  margin: 20px 0 18px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  border-left: 4px solid #0f766e;
}

.eyebrow {
  margin-bottom: 6px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
}

.tasks-hero h1 {
  margin-bottom: 8px;
  color: #111827;
  font-size: 26px;
}

.tasks-hero p,
.task-toolbar p,
.migration-card p,
.empty-card p,
.task-detail p,
.task-detail li {
  color: #4b5563;
  line-height: 1.7;
}

.hero-actions,
.toolbar-actions,
.empty-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-btn,
.empty-action {
  display: inline-block;
  padding: 10px 16px;
  border-radius: 8px;
}

.hero-btn.primary,
.empty-action.btn-primary {
  color: white;
}

.migration-card,
.task-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.plan-generator {
  display: grid;
  gap: 16px;
  margin-bottom: 14px;
  border-left: 4px solid #111827;
}

.generator-head,
.generator-actions,
.draft-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.generator-head h2 {
  margin: 0 0 8px;
  color: #111827;
  font-size: 20px;
}

.generator-head p,
.generator-meta {
  color: #4b5563;
  line-height: 1.7;
}

.generator-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.generator-grid label,
.draft-item label {
  display: grid;
  gap: 6px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

.generator-actions {
  align-items: center;
  flex-wrap: wrap;
}

.switch-inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

.switch-inline input {
  width: auto;
}

.generator-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.generator-meta span {
  padding: 4px 9px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 12px;
  font-weight: 700;
}

.draft-list {
  display: grid;
  gap: 12px;
}

.draft-item {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}

.draft-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.progress-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.progress-card {
  display: grid;
  gap: 6px;
}

.progress-card span {
  color: #6b7280;
  font-size: 13px;
}

.progress-card strong {
  color: #111827;
  font-size: 24px;
}

.filter-card {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.filter-card label {
  display: grid;
  gap: 6px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

.task-toolbar h2 {
  color: #111827;
  margin-bottom: 4px;
}

.hidden-input {
  display: none;
}

.danger-outline {
  color: #991b1b;
  background: #fee2e2;
}

.message {
  margin-bottom: 14px;
  font-size: 13px;
}

.message.success {
  color: #047857;
}

.message.error {
  color: #dc2626;
}

.empty-card {
  text-align: center;
  padding: 48px 24px;
}

.empty-card h2 {
  margin-bottom: 8px;
}

.empty-actions {
  justify-content: center;
  margin-top: 16px;
}

.task-list {
  display: grid;
  gap: 14px;
}

.task-card {
  display: grid;
  gap: 14px;
}

.task-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.task-check {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #111827;
  font-weight: 700;
}

.task-check input {
  width: auto;
}

.task-check .done {
  color: #6b7280;
  text-decoration: line-through;
}

.remove-btn {
  padding: 6px 10px;
  border-radius: 6px;
  color: #6b7280;
  background: #f3f4f6;
}

.remove-btn:hover {
  color: #991b1b;
  background: #fee2e2;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-meta span {
  padding: 4px 9px;
  border-radius: 999px;
  color: #374151;
  background: #f3f4f6;
  font-size: 12px;
  font-weight: 600;
}

.task-detail {
  display: grid;
  gap: 10px;
}

.task-detail strong {
  display: block;
  margin-bottom: 4px;
  color: #111827;
  font-size: 13px;
}

.route-source {
  margin-top: 4px;
  font-size: 12px;
}

.task-detail ul {
  margin-left: 18px;
}

.task-notes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.task-notes label {
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.task-notes textarea {
  min-height: 86px;
  resize: vertical;
}

@media (max-width: 760px) {
  .tasks-hero,
  .migration-card,
  .task-toolbar,
  .generator-head,
  .generator-actions,
  .task-head {
    flex-direction: column;
    align-items: stretch;
  }

  .task-notes {
    grid-template-columns: 1fr;
  }

  .progress-grid,
  .filter-card,
  .generator-grid,
  .draft-grid {
    grid-template-columns: 1fr;
  }
}
</style>
