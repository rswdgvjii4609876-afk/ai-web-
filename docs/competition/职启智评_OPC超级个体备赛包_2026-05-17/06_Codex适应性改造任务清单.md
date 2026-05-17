# Codex 适应性改造任务清单

## P0：必须完成

### 任务 1：新增 OPC 参赛材料目录

新增目录：

```text
docs/competition/opc/
```

新增文件：

```text
README_OPC参赛总入口.md
01_赛事适配判断.md
02_OPC参赛主叙事.md
03_AI工作流总图.md
04_人机协同分工图.md
05_复赛集中限时实测训练包.md
06_答辩PPT_OPC版页面结构.md
07_三分钟讲稿_OPC版.md
08_八分钟讲稿_OPC版.md
09_评委问答库_OPC版.md
10_一人OPC日常运行手册.md
11_三个月补实路线.md
12_可展示成果与不能夸大边界.md
```

验收：每个文件不能空泛，必须结合职启智评现有功能。

---

### 任务 2：补齐 Agent 角色卡

检查 `docs/agents/`，补齐以下 Agent：

```text
OPC Commander Agent
Competition Research Agent
Codex Engineering Agent
Architecture Review Agent
Resume Evidence Agent
Role Profile RAG Agent
Gap Diagnosis Agent
Resume Polish Agent
Interviewer Agent
Learning Plan Agent
Report Review Agent
Data Governance Agent
Eval Judge Agent
SFT Dataset Agent
Defense Coach Agent
```

验收：每个 Agent 都要写明“人负责什么、AI 负责什么、输出什么、如何失败兜底”。

---

### 任务 3：生成复赛集中限时实测训练包

新增：

```text
docs/competition/opc/live_test_drills/
```

包含：

```text
drill_01_30分钟构建AI工作流.md
drill_02_45分钟重构人机协同结构.md
drill_03_60分钟垂直场景落地方案.md
drill_评分表.md
drill_我的标准作答模板.md
```

验收：这些文件必须能让参赛者直接拿来练。

---

### 任务 4：改造 PPT 主线文档

新增或更新：

```text
docs/competition/opc/06_答辩PPT_OPC版页面结构.md
```

页面结构建议：

```text
1. 我是谁：OPC 超级个体
2. 我解决什么行业问题：高校就业服务
3. 我如何拆解工作：AI 原生工作流
4. 我如何人机协同：人和 AI 分工
5. 我的系统底座：职启智评可运行原型
6. 我的 Agent 编排：Career-AgentOS
7. 我的演示：三岗位 Trace
8. 我的轻量治理：一个人 + AI 替代小团队
9. 我的阶段成果：Preview、Eval、SFT-ready
10. 我的三个月补实路线
```

---

### 任务 5：更新任务记忆

必须更新：

```text
PROJECT_MEMORY.md
任务记录文档.md
docs/competition/职启智评项目升级流程手册.md
```

阶段标题：

```text
阶段 165：OPC 超级个体参赛叙事与 AI 工作流备赛包生成
```

## P1：建议完成

### 任务 6：新增 OPC 工作流 Trace 导出脚本

新增或复用：

```text
ai-interview-backend/app/scripts/generate_opc_assets.py
```

输出：

```text
artifacts/opc/opc_workflow_trace.md
artifacts/opc/opc_workflow_trace.json
artifacts/opc/ppt_opc_assets.md
```

Trace 必须覆盖：

```text
OPC Commander
Competition Research
Codex Engineering
Resume Evidence
Role Profile RAG
Gap Diagnosis
Resume Polish
Interviewer
Learning Plan
Report Review
Data Governance
Eval Judge
SFT Dataset
Defense Coach
```

### 任务 7：前端展示页增加 OPC 说明卡

如已有 `/competition/agent-trace`，在页面顶部增加：

```text
OPC 超级个体说明卡
- 我作为人负责什么
- AI Agents 负责什么
- 当前 trace 如何证明工作流
```

不做大改，不破坏现有页面。

## P2：三个月补实

```text
1. 完成 C1/C2/C3 真实闭环。
2. 补足真实授权样本和后台人工评分。
3. 启动 OpenAI SFT 或替代性 Prompt/RAG Eval。
4. 做 1 个高校就业服务小范围试点。
5. 形成阶段性成果输出：升级版 AI 原生结构说明、场景对接方案、实践计划。
```
