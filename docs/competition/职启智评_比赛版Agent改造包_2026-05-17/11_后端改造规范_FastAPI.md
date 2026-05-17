# 后端改造规范：FastAPI + Agent Orchestrator

## 1. 改造原则

```text
不重写现有业务主链路。
先新增比赛展示层。
所有新增模块可独立运行。
不依赖真实 OpenAI Key 也能 demo。
```

---

## 2. 推荐目录

```text
app/services/agent_orchestrator/
  __init__.py
  schemas.py
  registry.py
  orchestrator.py
  trace_logger.py
  demo_pipeline.py
  prompts.py

app/scripts/
  generate_demo_cases.py
  export_agent_trace.py
  run_interview_eval_preview.py
  build_sft_preview.py
  generate_competition_assets.py
```

---

## 3. schemas.py 建议

```python
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class EvidenceItem(BaseModel):
    ability: str
    resume_evidence: str
    evidence_status: str
    risk: str
    interview_focus: str

class RoleAbility(BaseModel):
    ability: str
    required_level: str
    why_important: str

class GapItem(BaseModel):
    ability: str
    required_level: str
    evidence_status: str
    gap_level: str
    diagnosis: str
    next_question_focus: str

class ResumePolishSuggestion(BaseModel):
    section: str
    original_issue: str
    polish_suggestion: str
    evidence_constraint: str
    missing_evidence_to_prepare: List[str] = Field(default_factory=list)

class InterviewQuestion(BaseModel):
    question: str
    target_ability: str
    evidence_focus: str
    reason: str
    expected_answer_elements: List[str]

class EvalScore(BaseModel):
    focus_score: int
    evidence_score: int
    depth_score: int
    polish_score: int
    role_fit_score: int
    format_score: int
    report_score: int
    total_score: int
    judge_note: str

class AgentStep(BaseModel):
    step: int
    agent: str
    title: str
    output: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)

class AgentTrace(BaseModel):
    trace_id: str
    case_id: str
    target_role: str
    sample_origin: str
    for_training: bool = False
    for_competition_demo: bool = True
    steps: List[AgentStep]
```

---

## 4. demo_pipeline.py 建议

第一版可以不调用大模型，直接用规则和模板生成稳定演示资产。

```python
def run_demo_pipeline(case: dict) -> AgentTrace:
    evidence = build_resume_evidence(case)
    role_profile = build_role_profile(case)
    gaps = build_gap_matrix(evidence, role_profile)
    polish = build_resume_polish(case, evidence, role_profile, gaps)
    question = build_interview_question(case, gaps)
    report = build_report_summary(case, gaps, question)
    eval_score = score_question_and_polish(question, polish, gaps)
    return build_trace(case, evidence, role_profile, gaps, polish, question, report, eval_score)
```

后续再把 `build_resume_polish` 和 `build_interview_question` 替换为真实 LLM 调用。润色输出必须继承现有 `/resume-polish` 的证据约束：不编造项目、公司、时间、指标或技术经历。

---

## 5. trace_logger.py 建议

功能：

```text
save_trace_json(trace, path)
export_trace_markdown(trace, path)
```

Markdown 输出必须适合截图放 PPT。

---

## 6. API 设计建议

如果要接入 FastAPI，新增：

```text
GET /api/v1/competition/demo-cases
POST /api/v1/competition/agent-trace/run
GET /api/v1/competition/agent-trace/{trace_id}
GET /api/v1/competition/eval-preview/{trace_id}
GET /api/v1/competition/sft-preview/{trace_id}
```

返回数据只用演示样例即可，不影响真实业务。

---

## 7. 数据库是否必须改

赛前不必须。

优先用文件：

```text
demo_cases/*.json
artifacts/agent_trace/*.json
artifacts/eval/*.csv
artifacts/sft_preview/*.jsonl
```

三个月内再补数据库表：

```text
agent_runs
agent_steps
sample_registry
eval_runs
eval_scores
sft_dataset_runs
```

---

## 8. 脚本输出规范

所有脚本必须支持：

```text
--out
--case 或 --input
--demo-mode
```

所有生成文件必须带清楚状态：

```json
{
  "sample_origin": "demo_constructed",
  "for_training": false,
  "for_competition_demo": true
}
```

---

## 9. 最小验收命令

```bash
python -m app.scripts.generate_competition_assets
```

执行后存在：

```text
demo_cases/python_backend.json
artifacts/agent_trace/python_backend.trace.md
artifacts/eval/eval_score_table.csv
artifacts/sft_preview/train.preview.jsonl
```
