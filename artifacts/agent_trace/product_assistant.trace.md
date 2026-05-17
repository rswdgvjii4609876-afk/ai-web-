# Career-AgentOS Agent Trace：产品助理/产品经理实习生

- case_id：`product_assistant`
- sample_origin：`demo_constructed`
- for_training：`false`
- for_competition_demo：`true`

> 本 Trace 为比赛演示沙盘和 Preview，不代表真实用户样本或真实 OpenAI 微调结果。

## Step 1：简历证据链

- Agent：`ResumeEvidenceAgent`

```json
{
  "evidence_items": [
    {
      "ability": "需求分析",
      "resume_evidence": "出现问卷、访谈、功能清单和流程图",
      "evidence_status": "indirect",
      "risk": "需要验证是否真正参与需求拆解",
      "interview_focus": "需求来源、用户场景、优先级取舍"
    },
    {
      "ability": "PRD 输出",
      "resume_evidence": "只提到原型草稿，没有明确 PRD 文档或验收标准",
      "evidence_status": "claimed_only",
      "risk": "产品文档能力证据不足",
      "interview_focus": "PRD 结构、验收标准、边界条件"
    },
    {
      "ability": "数据意识",
      "resume_evidence": "简历未说明上线指标、转化率或反馈数据",
      "evidence_status": "missing",
      "risk": "缺少功能效果复盘能力",
      "interview_focus": "指标设计、数据复盘、功能迭代"
    }
  ]
}
```

## Step 2：岗位画像

- Agent：`RoleProfileAgent`

```json
{
  "core_abilities": [
    "需求分析",
    "PRD 输出",
    "竞品分析",
    "跨部门沟通",
    "数据意识"
  ],
  "role_requirements": [
    "能把模糊需求拆成场景、用户故事和验收标准",
    "能说明 PRD 的结构和优先级取舍",
    "能用数据或反馈验证功能效果"
  ]
}
```

## Step 3：能力差距

- Agent：`GapAnalysisAgent`

```json
{
  "gaps": [
    {
      "ability": "需求分析",
      "required_level": "目标岗位核心能力",
      "evidence_status": "indirect",
      "gap_level": "低",
      "diagnosis": "需要验证是否真正参与需求拆解",
      "next_question_focus": "需求来源、用户场景、优先级取舍"
    },
    {
      "ability": "PRD 输出",
      "required_level": "目标岗位核心能力",
      "evidence_status": "claimed_only",
      "gap_level": "中",
      "diagnosis": "产品文档能力证据不足",
      "next_question_focus": "PRD 结构、验收标准、边界条件"
    },
    {
      "ability": "数据意识",
      "required_level": "目标岗位核心能力",
      "evidence_status": "missing",
      "gap_level": "高",
      "diagnosis": "缺少功能效果复盘能力",
      "next_question_focus": "指标设计、数据复盘、功能迭代"
    }
  ]
}
```

## Step 4：证据约束简历润色

- Agent：`ResumePolishAgent`

**风险提示**

- PRD 输出 证据不足，不能写成已经独立完成相关项目。
- 数据意识 证据不足，不能写成已经独立完成相关项目。

```json
{
  "overall_strategy": "围绕目标岗位强化已证明经历；对仅声明或缺失能力，只给补证据建议，不写成已完成经历。",
  "section_suggestions": [
    {
      "section": "项目经历",
      "original_issue": "项目描述有技术或任务关键词，但缺少职责、动作和结果。",
      "polish_suggestion": "将真实经历改写为“负责模块 + 采取动作 + 协作对象 + 可验证结果”的表达。",
      "evidence_constraint": "只能使用简历已有项目和用户可证明事实，不新增公司、时间、技术栈或指标。",
      "missing_evidence_to_prepare": [
        "PRD 输出",
        "数据意识"
      ]
    }
  ],
  "risk_warnings": [
    "PRD 输出 证据不足，不能写成已经独立完成相关项目。",
    "数据意识 证据不足，不能写成已经独立完成相关项目。"
  ]
}
```

## Step 5：证据追问

- Agent：`InterviewFollowupAgent`

```json
{
  "question": "你目标岗位需要PRD 输出能力，但简历证据状态是“claimed_only”。请结合一个真实项目说明：当时的场景是什么，你负责哪一部分，采取了什么行动，结果如何验证？如果没有实际经历，也请说明你准备如何补齐这个证据。",
  "target_ability": "PRD 输出",
  "evidence_focus": "claimed_only",
  "reason": "产品文档能力证据不足",
  "expected_answer_elements": [
    "具体场景",
    "个人职责",
    "行动方案",
    "结果或指标",
    "证据补齐计划"
  ]
}
```

## Step 6：报告摘要

- Agent：`ReportAgent`

```json
{
  "summary": "产品助理/产品经理实习生演示样本已形成证据链、能力缺口、润色建议和追问目标。",
  "top_gaps": [
    "PRD 输出",
    "数据意识"
  ],
  "next_actions": [
    "补齐证据材料",
    "完成三轮模拟面试",
    "将授权样本交由后台人工评分"
  ]
}
```

## Step 7：学习任务

- Agent：`LearningTaskAgent`

```json
{
  "tasks": [
    {
      "title": "补齐需求分析证据",
      "practice": "需求来源、用户场景、优先级取舍",
      "acceptance": "能用 STAR 结构讲清一次真实经历或明确补证据计划"
    },
    {
      "title": "补齐PRD 输出证据",
      "practice": "PRD 结构、验收标准、边界条件",
      "acceptance": "能用 STAR 结构讲清一次真实经历或明确补证据计划"
    }
  ]
}
```

## Step 8：数据治理

- Agent：`DataGovernanceAgent`

```json
{
  "sample_origin": "demo_constructed",
  "for_training": false,
  "for_competition_demo": true,
  "claim": "演示样本只用于比赛展示和链路验证，不作为真实训练样本。"
}
```

## Step 9：Eval Preview

- Agent：`EvalAgent`

```json
{
  "focus_score": 5,
  "evidence_score": 5,
  "depth_score": 5,
  "polish_score": 5,
  "role_fit_score": 4,
  "format_score": 5,
  "report_score": 5,
  "total_score": 34,
  "judge_note": "Preview rule score for competition demo only; it is not a real holdout eval."
}
```

## Step 10：SFT Preview 摘要

- Agent：`SFTPreviewAgent`

```json
{
  "dataset_type": "sft_preview",
  "ready_for_real_training": false,
  "preview_tasks": [
    "interview_followup",
    "evidence_bound_resume_polish"
  ]
}
```

## Eval Preview

```json
{
  "focus_score": 5,
  "evidence_score": 5,
  "depth_score": 5,
  "polish_score": 5,
  "role_fit_score": 4,
  "format_score": 5,
  "report_score": 5,
  "total_score": 34,
  "judge_note": "Preview rule score for competition demo only; it is not a real holdout eval."
}
```
