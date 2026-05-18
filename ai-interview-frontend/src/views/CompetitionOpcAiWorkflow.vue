<template>
  <div class="opc-page">
    <header class="hero">
      <div>
        <p class="eyebrow">OPC AI 协同展示页</p>
        <h1>一个人调度多 AI Agents 的就业服务工作流</h1>
        <p class="lead">
          本页展示职启智评 OPC 的 AI 协同结构：我作为 OPC Commander 负责目标、真实性、授权、评分标准和最终验收；AI 负责高频生成、检索、工程执行和初步评估。
        </p>
      </div>
      <div class="hero-card">
        <span>当前状态</span>
        <strong>Preview / Demo</strong>
        <p>不是正式训练结果，不包含真实用户数据。</p>
      </div>
    </header>

    <section class="boundary">
      <strong>边界说明</strong>
      <span>
        本页内容来自 OPC 备赛材料、AI 协同样例和 Career-AgentOS Preview。所有样例仅用于说明工作流格式，不代表真实后训练、真实用户数据或真实闭环验收结果。
      </span>
    </section>

    <section class="console-bar" aria-label="OPC 展示状态">
      <div v-for="item in statusItems" :key="item.label" class="console-chip">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>

    <section class="workflow-card">
      <div class="section-head">
        <div>
          <p class="eyebrow">Workflow</p>
          <h2>AI 协同链路</h2>
        </div>
        <router-link class="ghost-link" to="/competition/agent-trace">查看三岗位 Agent Trace</router-link>
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

    <section class="panel trace-bridge">
      <div>
        <p class="eyebrow">Career-AgentOS Connection</p>
        <h2>连接三岗位 Agent Trace</h2>
        <p>
          OPC 工作流页说明“一个人如何调度 AI”，三岗位 Agent Trace 说明“调度后的业务链路如何落到简历、润色、追问、报告、Eval 和 SFT Preview”。
        </p>
      </div>
      <router-link class="primary-link" to="/competition/agent-trace">打开三岗位 Preview</router-link>
    </section>

    <section class="grid two">
      <article class="panel">
        <div class="section-head compact">
          <div>
            <p class="eyebrow">Human-AI Boundary</p>
            <h2>人机协同分工</h2>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>工作项</th>
                <th>AI 负责</th>
                <th>人负责</th>
                <th>验收证据</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in boundaryRows" :key="item.task">
                <td>{{ item.task }}</td>
                <td>{{ item.ai }}</td>
                <td>{{ item.human }}</td>
                <td>{{ item.evidence }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel">
        <div class="section-head compact">
          <div>
            <p class="eyebrow">Agent Matrix</p>
            <h2>Agent 分工矩阵</h2>
          </div>
        </div>
        <div class="agent-list">
          <article v-for="agent in agents" :key="agent.name" class="agent-item">
            <div>
              <h3>{{ agent.name }}</h3>
              <p>{{ agent.input }} -> {{ agent.output }}</p>
            </div>
            <span>{{ agent.guardrail }}</span>
          </article>
        </div>
      </article>
    </section>

    <section class="grid three">
      <article v-for="asset in evidenceAssets" :key="asset.name" class="panel asset">
        <p class="eyebrow">{{ asset.type }}</p>
        <h2>{{ asset.name }}</h2>
        <p>{{ asset.description }}</p>
        <code>{{ asset.path }}</code>
        <pre class="sample-snippet">{{ asset.snippet }}</pre>
      </article>
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

    <section class="panel">
      <div class="section-head compact">
        <div>
          <p class="eyebrow">Claim Boundary</p>
          <h2>答辩可说与不可说</h2>
        </div>
      </div>
      <div class="claim-grid">
        <div>
          <h3>可以说</h3>
          <ul>
            <li v-for="item in allowedClaims" :key="item">{{ item }}</li>
          </ul>
        </div>
        <div>
          <h3>不能说</h3>
          <ul>
            <li v-for="item in blockedClaims" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
const statusItems = [
  { label: '页面类型', value: 'OPC Preview' },
  { label: '样本来源', value: 'sample format only' },
  { label: '训练用途', value: 'for_training=false' },
  { label: '下一步', value: '166.5 OPC PPT' }
]

const workflowNodes = [
  {
    title: 'OPC Commander',
    description: '确定参赛目标、真实边界、隐私授权和最终验收标准。',
    output: '任务优先级与验收口径'
  },
  {
    title: 'ChatGPT 策略 AI',
    description: '提炼赛道要求、拆解叙事结构、生成问答和 Prompt 草案。',
    output: 'OPC 叙事与任务包'
  },
  {
    title: 'Codex 工程 AI',
    description: '把任务落成代码、脚本、文档、测试和 Git 记录。',
    output: '可运行页面与工程证据'
  },
  {
    title: '业务大模型',
    description: '支持简历诊断、岗位画像、简历润色、面试追问、报告复盘和学习任务。',
    output: '就业训练业务结果'
  },
  {
    title: 'Eval / 后台评分',
    description: '检查输出质量、样本准入、PII 风险和人工评分状态。',
    output: 'Preview 评估与门禁'
  },
  {
    title: '人工验收',
    description: '确认真实性、合规边界、评分标准和最终提交材料。',
    output: '可答辩、可追溯交付'
  }
]

const boundaryRows = [
  {
    task: '赛道理解',
    ai: '搜索资料、提炼评审重点、生成叙事草案',
    human: '判断是否符合项目真实状态',
    evidence: 'OPC 赛事适配判断'
  },
  {
    task: '工程实现',
    ai: '生成页面、脚本、测试和文档修改方案',
    human: '审查是否破坏主链路并决定是否提交',
    evidence: 'Git 提交与构建输出'
  },
  {
    task: '业务生成',
    ai: '生成岗位画像、润色建议、追问和报告',
    human: '确认不编造经历、不越过授权',
    evidence: 'Agent Trace 与后台复核'
  },
  {
    task: '质量评估',
    ai: '执行规则评分、样本准入和风险提示',
    human: '制定评分标准并决定是否纳入样本',
    evidence: 'Eval Preview 与人工评分'
  }
]

const agents = [
  {
    name: 'Competition Research Agent',
    input: '赛事通知、项目状态',
    output: '评审重点与答辩主线',
    guardrail: '不夸大赛道要求'
  },
  {
    name: 'Codex Engineering Agent',
    input: '任务清单、代码仓库',
    output: '页面、脚本、测试、提交',
    guardrail: '不破坏主链路'
  },
  {
    name: 'Resume Polish Agent',
    input: '简历证据、岗位画像、能力差距',
    output: '可改但不造假的润色建议',
    guardrail: '不新增未经证明经历'
  },
  {
    name: 'Eval Agent',
    input: 'Trace、问答、报告、样本标记',
    output: 'Preview 评分与风险提示',
    guardrail: '不替代真实 holdout 评估'
  },
  {
    name: 'SFT Dataset Agent',
    input: '授权样本、人工复核、脱敏结果',
    output: 'SFT-ready 数据门禁',
    guardrail: '未授权不进入训练'
  },
  {
    name: 'Defense Coach Agent',
    input: 'PPT、讲稿、问答库',
    output: '评委问答和边界话术',
    guardrail: '不包装未完成成果'
  }
]

const evidenceAssets = [
  {
    type: 'Prompt Chain',
    name: 'AI Prompt 交接样例',
    description: '说明 ChatGPT、Codex 和业务模型之间如何传递任务。',
    path: 'artifacts/opc_ai_coordination/ai_prompt_chain.sample.md',
    snippet: 'input: OPC 赛事通知 + 项目状态\noutput: OPC 叙事、PPT Brief、问答库\nreview: 人工删除夸大表述'
  },
  {
    type: 'Codex Task',
    name: 'Codex 任务包样例',
    description: '说明工程任务如何从需求变成文件、测试和提交。',
    path: 'artifacts/opc_ai_coordination/codex_task_bundle.sample.md',
    snippet: 'scope: docs/competition/opc + frontend preview\nchecks: npm run build + 文案扫描\ncommit: 精准暂存，不使用 git add .'
  },
  {
    type: 'Handoff Log',
    name: 'AI 交接日志样例',
    description: '说明人和 AI 如何记录任务输入、输出和验收点。',
    path: 'artifacts/opc_ai_coordination/ai_handoff_log.sample.md',
    snippet: 'from: ChatGPT strategy\nTo: Codex engineering\nacceptance: 页面可访问、边界清晰、无真实数据'
  }
]

const drills = [
  {
    time: '30 分钟',
    title: '构建新岗位 AI 工作流',
    output: '场景识别 -> Agent 分工 -> 输出物定义 -> 质量门禁'
  },
  {
    time: '45 分钟',
    title: '重构人机协同结构',
    output: '把小团队角色映射为 OPC Commander 与 AI Agents'
  },
  {
    time: '60 分钟',
    title: '垂直场景落地方案',
    output: '迁移到路演训练、导师面试训练等相邻场景'
  }
]

const allowedClaims = [
  '已形成可运行原型和 Career-AgentOS Preview。',
  '已完成 OPC AI 协同工作流备赛包和证据格式样例。',
  '已具备 Agent Trace、Eval Preview、SFT-ready 门禁的展示链路。',
  '真实训练、真实样本和高校试点进入三个月补实路线。'
]

const blockedClaims = [
  '不能说已经完成官方后训练任务。',
  '不能说三岗位真实闭环已经全部验收。',
  '不能说 demo 或 constructed 样本来自真实用户。',
  '不能把 Eval Preview 说成真实模型实测。'
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
.workflow-card,
.panel,
.boundary {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
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
  max-width: 780px;
  margin: 12px 0 0;
  color: #475569;
  line-height: 1.75;
}

.hero-card {
  padding: 18px;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
}

.hero-card span,
.hero-card p {
  color: #64748b;
  font-size: 13px;
}

.hero-card strong {
  display: block;
  margin: 10px 0;
  color: #0f766e;
  font-size: 22px;
}

.boundary {
  display: flex;
  gap: 12px;
  margin: 16px 0;
  padding: 14px 16px;
  border-left: 4px solid #0f766e;
  color: #374151;
  line-height: 1.7;
}

.console-bar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.console-chip {
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
}

.console-chip span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.console-chip strong {
  display: block;
  margin-top: 6px;
  color: #1e3a8a;
  font-size: 15px;
  overflow-wrap: anywhere;
}

.workflow-card,
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

.primary-link {
  flex-shrink: 0;
  padding: 10px 14px;
  border-radius: 8px;
  background: #0f766e;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

.trace-bridge {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  background: #f0fdfa;
  border-color: #99f6e4;
}

.trace-bridge p {
  max-width: 760px;
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.7;
}

.workflow {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.workflow-node,
.agent-item,
.drill,
.asset {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.workflow-node {
  position: relative;
  min-height: 190px;
  padding: 14px;
}

.node-index {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
  border-radius: 999px;
  background: #ccfbf1;
  color: #0f766e;
  font-weight: 800;
}

.workflow-node p,
.agent-item p,
.asset p,
.drill p {
  color: #475569;
  font-size: 13px;
  line-height: 1.65;
}

.workflow-node strong {
  display: block;
  margin-top: 10px;
  color: #1e40af;
  font-size: 13px;
}

.grid {
  display: grid;
  gap: 16px;
}

.grid.two {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
}

.grid.three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 680px;
}

th,
td {
  padding: 10px;
  border: 1px solid #e5e7eb;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
  line-height: 1.6;
}

th {
  background: #f1f5f9;
  color: #0f172a;
}

.agent-list {
  display: grid;
  gap: 10px;
}

.agent-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
}

.agent-item span {
  flex-shrink: 0;
  align-self: flex-start;
  max-width: 130px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  line-height: 1.4;
}

.asset {
  padding: 16px;
}

code {
  display: block;
  padding: 8px;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.5;
  white-space: normal;
  word-break: break-all;
}

.sample-snippet {
  min-height: 112px;
  max-height: 180px;
  margin-top: 10px;
  padding: 10px;
  border-radius: 8px;
  background: #020617;
  color: #dbeafe;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.drill-grid,
.claim-grid {
  display: grid;
  gap: 12px;
}

.drill-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.drill {
  padding: 14px;
}

.drill strong {
  color: #0f766e;
  font-size: 18px;
}

.claim-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

ul {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #374151;
  line-height: 1.75;
}

li {
  margin-bottom: 4px;
}

@media (max-width: 980px) {
  .hero,
  .console-bar,
  .grid.two,
  .grid.three,
  .drill-grid,
  .claim-grid {
    grid-template-columns: 1fr;
  }

  .workflow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .opc-page {
    padding: 18px 14px 36px;
  }

  .hero,
  .workflow-card,
  .panel {
    padding: 14px;
  }

  .workflow {
    grid-template-columns: 1fr;
  }

  .section-head,
  .boundary,
  .trace-bridge,
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
