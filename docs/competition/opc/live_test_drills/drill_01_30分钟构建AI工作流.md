# Drill 01：30 分钟构建 AI 工作流

## 题目

现场给定一个新岗位，例如“新媒体运营实习生”，请在 30 分钟内说明如何把它接入职启智评 OPC 工作流。

## 限时

30 分钟。

## 输入材料

- 岗位名称。
- 一段岗位 JD。
- 一份去标识化简历摘要。

## OPC 拆解

1. 确认岗位核心能力。
2. 标注简历证据状态：direct / indirect / claimed_only / missing。
3. 生成能力缺口。
4. 生成证据约束简历润色建议。
5. 生成 3 个面试追问。
6. 生成 3 个学习任务。
7. 给出数据治理和人工复核门禁。

## AI Agent 分工

- Competition Research Agent：判断岗位所属赛道和应用场景。
- Role Profile RAG Agent：抽取岗位能力模型。
- Resume Evidence Agent：生成证据状态。
- Gap Diagnosis Agent：输出能力差距。
- Resume Polish Agent：输出可改但不造假的润色建议。
- Interviewer Agent：输出证据追问。
- Learning Plan Agent：输出学习任务。
- Data Governance Agent：检查授权和样本准入。

## 最终交付物

- 一张 AI 工作流图。
- 一张 Agent 分工表。
- 一段 1 分钟现场讲解。

## 评分点

- 是否体现人机边界。
- 是否避免 AI 编造候选人经历。
- 是否能复用现有 Career-AgentOS。
- 是否有输出物和验收标准。

## 现场讲解话术

```text
我不会直接让 AI 生成面试题，而是先把岗位 JD 转成能力模型，再把候选人简历转成证据状态，之后才进入润色、追问和学习任务。人负责确认岗位选择和真实性，AI 负责高频拆解和初稿生成。
```
