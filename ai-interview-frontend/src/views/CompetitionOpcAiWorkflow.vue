<template>
  <div class="opc-page">
    <header class="hero">
      <div class="hero-main">
        <p class="eyebrow">评委演示页 / OPC Preview</p>
        <h1>职启智评 OPC：一个人 + AI Agents 构建高校就业能力诊断与训练服务单元</h1>
        <p class="lead">
          这页回答评委最关心的问题：一个参赛者如何把多类 AI 工具组织成可运行、可追踪、可验收的就业服务工作流。
          页面只展示 demo/preview 证据，不包含真实用户数据，也不代表真实 OpenAI 微调已完成。
        </p>
      </div>
      <aside class="hero-status">
        <span>现场定位</span>
        <strong>评委演示 / 录屏素材</strong>
        <p>正式用户端不展示入口；需要证明可运行时再打开隐藏 URL。</p>
      </aside>
    </header>

    <section class="signal-grid" aria-label="30 秒总览">
      <article v-for="item in openingSignals" :key="item.title" class="signal-card">
        <span>{{ item.label }}</span>
        <h2>{{ item.title }}</h2>
        <p>{{ item.description }}</p>
      </article>
    </section>

    <section class="workflow-card">
      <div class="section-head">
        <div>
          <p class="eyebrow">Human + AI Workflow</p>
          <h2>从目标拆解到人工验收的协同链路</h2>
        </div>
        <router-link class="ghost-link" to="/competition/agent-trace">打开三岗位证据附录</router-link>
      </div>
      <div class="workflow">
        <article v-for="(node, index) in workflowNodes" :key="node.title" class="workflow-node">
          <span class="node-index">{{ index + 1 }}</span>
          <h3>{{ node.title }}</h3>
          <p>{{ node.description }}</p>
          <strong>{{ node.output }}</strong>
        </article>
      </div>
    </section>

    <section class="case-chain">
      <div class="section-head compact">
        <div>
          <p class="eyebrow">Evidence Chain</p>
          <h2>评委能看到的完整业务证据链</h2>
        </div>
      </div>
      <div class="chain-line">
        <article v-for="item in caseChain" :key="item.title" class="chain-step">
          <span>{{ item.step }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </article>
      </div>
    </section>

    <section class="grid two">
      <article class="panel">
        <div class="section-head compact">
          <div>
            <p class="eyebrow">Human-AI Boundary</p>
            <h2>人机边界</h2>
          </div>
        </div>
        <div class="boundary-list">
          <article v-for="row in boundaryRows" :key="row.task" class="boundary-row">
            <h3>{{ row.task }}</h3>
            <p><strong>AI 做：</strong>{{ row.ai }}</p>
            <p><strong>人做：</strong>{{ row.human }}</p>
            <span>{{ row.evidence }}</span>
          </article>
        </div>
      </article>

      <article class="panel">
        <div class="section-head compact">
          <div>
            <p class="eyebrow">Agent Roles</p>
            <h2>关键 Agent 分工</h2>
          </div>
        </div>
        <div class="agent-list">
          <article v-for="agent in agents" :key="agent.name" class="agent-item">
            <div>
              <h3>{{ agent.name }}</h3>
              <p>{{ agent.role }}</p>
            </div>
            <span>{{ agent.guardrail }}</span>
          </article>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="section-head compact">
        <div>
          <p class="eyebrow">Evidence Assets</p>
          <h2>答辩可用证据素材</h2>
        </div>
      </div>
      <div class="asset-grid">
        <article v-for="asset in evidenceAssets" :key="asset.name" class="asset-card">
          <span>{{ asset.type }}</span>
          <h3>{{ asset.name }}</h3>
          <p>{{ asset.description }}</p>
          <code>{{ asset.path }}</code>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="section-head compact">
        <div>
          <p class="eyebrow">Live Test Bridge</p>
          <h2>复赛限时实测桥接</h2>
        </div>
      </div>
      <div class="drill-grid">
        <article v-for="drill in drills" :key="drill.time" class="drill">
          <strong>{{ drill.time }}</strong>
          <h3>{{ drill.title }}</h3>
          <p>{{ drill.output }}</p>
        </article>
      </div>
    </section>

    <section class="claim-bar">
      <strong>边界说明</strong>
      <span>
        本页只用于 OPC 答辩演示和录屏。可以说已形成 demo/preview 工作流和证据格式；不能把它表述为官方微调已落地、已取得微调模型标识、三岗位真实验收已完成，或 demo 样本来自真实用户。
      </span>
    </section>
  </div>
</template>

<script setup>
const openingSignals = [
  {
    label: '解决什么问题',
    title: '就业指导反馈难闭环',
    description: '学生常拿不到岗位化、证据化、可复训的反馈；老师或指导者也难以持续追踪训练质量。'
  },
  {
    label: '怎么创新',
    title: '一个人调度多 AI Agents',
    description: '参赛者负责目标、真实性、授权和验收；AI 负责拆解、生成、工程实现、初评和材料整理。'
  },
  {
    label: '演示什么证据',
    title: '三岗位 Trace + 规则门禁',
    description: '展示简历证据、岗位差距、润色建议、追问、报告、学习任务、规则门禁 Preview 和 JSONL Schema Preview。'
  },
  {
    label: '当前边界',
    title: 'Preview，不冒充真实训练',
    description: '演示样本为 demo_constructed；真实授权样本、人工评分和 OpenAI SFT 放入后续补实路线。'
  }
]

const workflowNodes = [
  {
    title: '目标拆解',
    description: '把赛事要求、项目真实状态和答辩限制拆成可执行任务。',
    output: '阶段任务、边界清单、验收标准'
  },
  {
    title: '工程落地',
    description: '把任务转成页面、脚本、接口、测试和可提交代码。',
    output: '可运行前端页、Preview 资产、构建结果'
  },
  {
    title: '就业诊断',
    description: '围绕简历证据、岗位画像、能力差距、润色和面试追问产出业务结果。',
    output: '证据链、追问、报告、学习任务'
  },
  {
    title: '质量评估',
    description: '用规则门禁检查聚焦度、证据约束、格式稳定和数据准入风险。',
    output: '规则门禁 Preview、PII 风险提示、样本门禁'
  },
  {
    title: '人工验收',
    description: '由人确认是否真实、是否合规、是否可用于答辩或后续训练。',
    output: '可追溯材料、答辩口径、后续补实路线'
  }
]

const caseChain = [
  { step: '01', title: '简历证据', description: '识别 direct / indirect / claimed_only / missing，不把岗位知识库写成个人经历。' },
  { step: '02', title: '岗位差距', description: '把目标岗位要求映射为能力缺口，形成后续追问和学习任务依据。' },
  { step: '03', title: '简历润色', description: '只做岗位化表达和补证据建议，不新增公司、项目、时间或指标。' },
  { step: '04', title: '面试追问', description: '围绕缺口能力追问具体场景、行动、结果和指标。' },
  { step: '05', title: '报告复盘', description: '输出能力诊断、改进建议、学习任务和训练复盘。' },
  { step: '06', title: '数据门禁', description: '区分 demo preview 与真实授权样本，真实训练前必须人工复核。' }
]

const boundaryRows = [
  {
    task: '赛事理解',
    ai: '检索资料、提炼评分点、生成叙事草案。',
    human: '判断哪些内容符合项目真实状态。',
    evidence: 'OPC 方案对比、Brief、审查报告'
  },
  {
    task: '工程实现',
    ai: '生成页面、脚本、测试和文档修改方案。',
    human: '审查范围、提交内容和是否破坏主链路。',
    evidence: 'Git 提交、构建输出、测试记录'
  },
  {
    task: '就业诊断',
    ai: '生成岗位画像、润色建议、追问和报告草稿。',
    human: '确认不编造经历、不越过授权边界。',
    evidence: 'Agent Trace、后台人工评分'
  },
  {
    task: '后训练准备',
    ai: '整理 JSONL 结构和样本门禁。',
    human: '确认授权、脱敏、复核和是否创建付费 job。',
    evidence: 'JSONL Schema Preview、后训练操作手册'
  }
]

const agents = [
  { name: 'OPC Commander', role: '确定目标、边界、验收口径和最终责任。', guardrail: '人负责最终判断' },
  { name: '工程执行 Agent', role: '把需求落成页面、脚本、测试和提交。', guardrail: '不破坏主链路' },
  { name: '简历润色 Agent', role: '根据证据和岗位画像给出可改但不造假的表达。', guardrail: '缺证据只提示补证据' },
  { name: '面试追问 Agent', role: '围绕能力缺口生成追问和期望回答要素。', guardrail: '不替候选人编经历' },
  { name: 'Eval Agent', role: '用规则门禁检查输出质量和风险。', guardrail: '不替代真实 holdout eval' },
  { name: 'SFT Dataset Agent', role: '预演 JSONL 结构和训练样本准入条件。', guardrail: '未授权不训练' }
]

const evidenceAssets = [
  {
    type: '运行页面',
    name: '三岗位证据附录',
    description: '展示 demo case、Agent 业务链路、规则门禁和 JSONL 结构预览。',
    path: '/competition/agent-trace'
  },
  {
    type: 'Trace 资产',
    name: 'Agent Trace JSON/Markdown',
    description: '用于追溯每个 Agent 的输入、判断、输出和边界。',
    path: 'artifacts/agent_trace/*.trace.json'
  },
  {
    type: 'OPC 材料',
    name: 'AI 协同工作流包',
    description: '记录 Prompt 交接、Codex 任务包、AI handoff log 和复赛实测训练。',
    path: 'docs/competition/opc_ai_coordination/'
  }
]

const drills = [
  {
    time: '30 分钟',
    title: '构建新岗位 AI 工作流',
    output: '从场景识别到 Agent 分工、输出物定义和质量门禁。'
  },
  {
    time: '45 分钟',
    title: '重构人机协同结构',
    output: '把传统小团队职责映射为 OPC Commander + AI Agents。'
  },
  {
    time: '60 分钟',
    title: '迁移到垂直场景',
    output: '把就业训练链路迁移到路演训练、导师面试或课程项目复盘。'
  }
]
</script>

<style scoped>
.opc-page {
  max-width: 1160px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  color: #111827;
}

.hero,
.signal-card,
.workflow-card,
.case-chain,
.panel,
.claim-bar {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  align-items: stretch;
  padding: 24px;
  background: linear-gradient(135deg, #f8fafc 0%, #ecfeff 100%);
}

.eyebrow {
  margin: 0 0 6px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 800;
}

h1,
h2,
h3,
p {
  overflow-wrap: anywhere;
}

h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
}

h2 {
  margin: 0;
  font-size: 20px;
}

h3 {
  margin: 0;
  font-size: 15px;
}

.lead {
  max-width: 820px;
  margin: 12px 0 0;
  color: #475569;
  line-height: 1.75;
}

.hero-status {
  padding: 18px;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
}

.hero-status span,
.hero-status p {
  color: #64748b;
  font-size: 13px;
}

.hero-status strong {
  display: block;
  margin: 10px 0;
  color: #0f766e;
  font-size: 21px;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.signal-card {
  padding: 16px;
}

.signal-card span {
  display: inline-block;
  margin-bottom: 8px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  font-weight: 800;
}

.signal-card p,
.workflow-node p,
.chain-step p,
.boundary-row p,
.agent-item p,
.asset-card p,
.drill p {
  color: #475569;
  font-size: 13px;
  line-height: 1.65;
}

.workflow-card,
.case-chain,
.panel {
  padding: 18px;
  margin-bottom: 16px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.section-head.compact {
  margin-bottom: 12px;
}

.ghost-link {
  flex-shrink: 0;
  padding: 8px 12px;
  border: 1px solid #0f766e;
  border-radius: 8px;
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.workflow,
.asset-grid,
.drill-grid {
  display: grid;
  gap: 10px;
}

.workflow {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.workflow-node,
.chain-step,
.boundary-row,
.agent-item,
.asset-card,
.drill {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.workflow-node {
  min-height: 178px;
  padding: 14px;
}

.node-index,
.chain-step span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #ccfbf1;
  color: #0f766e;
  font-weight: 800;
}

.node-index {
  width: 28px;
  height: 28px;
  margin-bottom: 10px;
}

.workflow-node strong {
  display: block;
  margin-top: 10px;
  color: #1e40af;
  font-size: 13px;
}

.chain-line {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.chain-step {
  padding: 14px;
}

.chain-step span {
  width: 34px;
  height: 24px;
  margin-bottom: 10px;
  font-size: 12px;
}

.grid {
  display: grid;
  gap: 16px;
}

.grid.two {
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
}

.boundary-list,
.agent-list,
.asset-grid {
  display: grid;
  gap: 10px;
}

.boundary-row,
.agent-item,
.asset-card,
.drill {
  padding: 14px;
}

.boundary-row p {
  margin: 8px 0 0;
}

.boundary-row span {
  display: inline-block;
  margin-top: 10px;
  color: #075985;
  font-size: 12px;
  font-weight: 700;
}

.agent-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.agent-item span {
  flex-shrink: 0;
  align-self: flex-start;
  max-width: 140px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  line-height: 1.4;
}

.asset-grid,
.drill-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.asset-card span {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

code {
  display: block;
  margin-top: 10px;
  padding: 8px;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.5;
  white-space: normal;
  word-break: break-all;
}

.drill strong {
  color: #0f766e;
  font-size: 18px;
}

.claim-bar {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-left: 4px solid #0f766e;
  color: #374151;
  line-height: 1.7;
}

@media (max-width: 1080px) {
  .signal-grid,
  .workflow,
  .chain-line,
  .asset-grid,
  .drill-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 780px) {
  .hero,
  .grid.two,
  .signal-grid,
  .workflow,
  .chain-line,
  .asset-grid,
  .drill-grid {
    grid-template-columns: 1fr;
  }

  .section-head,
  .claim-bar,
  .agent-item {
    display: block;
  }

  .ghost-link {
    display: inline-block;
    margin-top: 10px;
  }

  h1 {
    font-size: 24px;
  }
}
</style>
