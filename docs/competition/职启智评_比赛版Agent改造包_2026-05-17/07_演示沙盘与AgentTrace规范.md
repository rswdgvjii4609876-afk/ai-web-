# 演示沙盘与 Agent Trace 规范

## 1. 为什么要做沙盘演示

比赛现场不一定会稳定联网，也不一定适合现场等待大模型返回。

因此必须准备：

```text
三岗位沙盘样例
Agent Trace 文件
Eval 表格
SFT Preview 文件
演示录屏
```

这些资产用于保证：

```text
即使现场 API 不稳定，仍能完整展示技术闭环。
```

---

## 2. 三岗位沙盘案例

建议生成三个演示案例：

| Case | 岗位 | 展示重点 |
|---|---|---|
| C1 | Python 后端开发工程师 | Redis、SQL、接口、并发、排障追问 |
| C2 | 产品助理 / 产品经理实习生 | 需求分析、PRD、指标、竞品、沟通 |
| C3 | 人力资源专员 | 招聘漏斗、候选人沟通、面试组织、复盘 |

---

## 3. Demo Case Schema

```json
{
  "case_id": "demo_python_backend_001",
  "sample_origin": "demo_constructed",
  "for_training": false,
  "for_competition_demo": true,
  "target_role": "Python 后端开发工程师",
  "resume_summary": {
    "education": "某本科院校计算机相关专业",
    "projects": [
      "基于 Flask 的校园二手交易平台，负责部分接口开发和数据库表设计"
    ],
    "skills": ["Python", "Flask", "MySQL", "Linux 基础"],
    "constraints": ["不含姓名、手机号、邮箱、学号、详细地址"]
  },
  "role_profile": {
    "core_abilities": ["REST API", "MySQL", "Redis", "并发基础", "部署排障"]
  },
  "resume_polish": {
    "enabled": true,
    "rule": "基于证据状态给润色建议，缺失能力不得编造成真实经历"
  },
  "interview_context": []
}
```

---

## 4. Agent Trace 输出结构

Trace JSON：

```json
{
  "trace_id": "trace_demo_python_backend_001",
  "case_id": "demo_python_backend_001",
  "created_at": "2026-05-17T00:00:00+09:00",
  "steps": [
    {
      "step": 1,
      "agent": "ResumeEvidenceAgent",
      "title": "简历证据识别",
      "output": {}
    },
    {
      "step": 2,
      "agent": "RoleProfileRAGAgent",
      "title": "岗位画像检索",
      "output": {}
    },
    {
      "step": 3,
      "agent": "GapDiagnosisAgent",
      "title": "能力差距诊断",
      "output": {}
    },
    {
      "step": 4,
      "agent": "ResumePolishAgent",
      "title": "证据约束简历润色",
      "output": {}
    },
    {
      "step": 5,
      "agent": "InterviewerAgent",
      "title": "证据追问生成",
      "output": {}
    },
    {
      "step": 6,
      "agent": "ReportAgent",
      "title": "报告摘要生成",
      "output": {}
    },
    {
      "step": 7,
      "agent": "EvalJudgeAgent",
      "title": "追问质量评分",
      "output": {}
    }
  ]
}
```

Trace Markdown：

```text
# Agent Trace：Python 后端开发工程师

## Step 1 简历证据 Agent
...

## Step 2 岗位画像 Agent
...

## Step 3 能力差距 Agent
...

## Step 4 简历润色 Agent
...

## Step 5 AI 面试官 Agent
...

## Step 6 报告 Agent
...

## Step 7 Eval Judge Agent
...
```

---

## 5. 演示页面建议

新增一个“技术展示 / Career-AgentOS Trace”页面，展示：

```text
左侧：输入简历摘要 + 目标岗位
中间：Agent 步骤流
右侧：当前 Agent 输出
底部：简历润色建议 + Eval 分数 + SFT Preview 样本
```

如果来不及做页面，至少导出 Markdown 和截图。

---

## 6. 演示问题示例

### 普通问题

```text
请介绍一下你的后端项目。
```

### 证据追问问题

```text
你简历中提到参与过 Flask 接口开发，但没有看到 Redis 缓存或接口性能优化的明确证据。
请结合一个具体项目说明：你是否处理过接口响应慢、缓存一致性或高并发访问问题？当时你负责哪一部分？采取了什么方案？最终指标如何变化？
```

PPT 展示时强调：

```text
职启智评的问题不是模板题，而是由岗位画像和证据缺口共同生成。
```

---

## 7. 生成脚本建议

### generate_demo_cases.py

输出：

```text
demo_cases/python_backend.json
demo_cases/product_assistant.json
demo_cases/hr_specialist.json
```

要求：

```text
sample_origin=demo_constructed
for_training=false
for_competition_demo=true
不含真实个人身份信息
```

### export_agent_trace.py

输入：

```text
demo_cases/python_backend.json
```

输出：

```text
artifacts/agent_trace/python_backend.trace.json
artifacts/agent_trace/python_backend.trace.md
```

### run_interview_eval_preview.py

输出：

```text
artifacts/eval/eval_score_table.csv
artifacts/eval/eval_summary.md
```

### build_sft_preview.py

输出：

```text
artifacts/sft_preview/train.preview.jsonl
artifacts/sft_preview/validation.preview.jsonl
artifacts/sft_preview/summary.preview.json
```

---

## 8. 演示录屏脚本

```text
1. 打开首页，说明项目定位。
2. 选择 Python 后端岗位。
3. 加载演示简历。
4. 展示简历证据链。
5. 展示岗位画像能力要求。
6. 展示能力缺口矩阵。
7. 展示证据约束简历润色建议。
8. 点击生成 AI 面试追问。
9. 展示证据追问问题。
10. 展示报告摘要和学习任务。
11. 切到后台或技术展示页，展示 Eval 和 SFT Preview。
```

---

## 9. 沙盘样例状态表述

建议在内部文件中标记：

```text
for_competition_demo=true
sample_origin=demo_constructed
```

PPT 上可以说：

```text
下面通过一个 Python 后端岗位的演示案例，展示系统如何完成从简历证据到能力缺口、证据约束简历润色，再到证据追问和训练样本沉淀的完整流程。
```

这样既能展示效果，也方便后续替换为真实授权案例。
