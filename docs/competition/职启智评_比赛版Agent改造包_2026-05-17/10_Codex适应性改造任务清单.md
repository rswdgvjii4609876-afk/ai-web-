# Codex 适应性改造任务清单

## 总目标

在现有项目基础上新增“比赛展示层”和“后续可补实工程入口”，不要重写项目。

---

## P0：文档与答辩资产

### 任务 P0-1：创建 competition 文档

新增：

```text
docs/competition/PPT主线.md
docs/competition/PPT页面大纲.md
docs/competition/三分钟讲稿.md
docs/competition/八分钟讲稿.md
docs/competition/评委问答库.md
docs/competition/演示脚本.md
docs/competition/通俗手册_原项目改了什么创新点在哪.md
```

验收：

```text
可以直接用于制作 PPT 和答辩。
```

---

### 任务 P0-2：创建 Agent 角色文档

新增：

```text
docs/agents/00_OPC总控Agent.md
docs/agents/01_比赛叙事Agent.md
docs/agents/02_简历证据Agent.md
docs/agents/03_岗位画像Agent.md
docs/agents/04_能力差距Agent.md
docs/agents/05_面试追问Agent.md
docs/agents/06_报告生成Agent.md
docs/agents/07_学习任务Agent.md
docs/agents/08_数据治理Agent.md
docs/agents/09_Eval评估Agent.md
docs/agents/10_后训练路线Agent.md
docs/agents/11_评委拷问Agent.md
```

验收：

```text
每个文件包含角色、输入、输出、约束、示例。
```

---

## P1：演示资产脚本

### 任务 P1-1：生成 demo cases

新增脚本：

```text
app/scripts/generate_demo_cases.py
```

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
无真实身份信息
```

命令：

```bash
python -m app.scripts.generate_demo_cases --out demo_cases
```

---

### 任务 P1-2：导出 Agent Trace

新增脚本：

```text
app/scripts/export_agent_trace.py
```

输入：

```text
demo_cases/python_backend.json
```

输出：

```text
artifacts/agent_trace/python_backend.trace.json
artifacts/agent_trace/python_backend.trace.md
```

命令：

```bash
python -m app.scripts.export_agent_trace --case demo_cases/python_backend.json --out artifacts/agent_trace
```

Trace 必须包含：

```text
简历证据
岗位画像
能力差距
面试追问
报告摘要
Eval 评分
SFT Preview 摘要
```

---

### 任务 P1-3：生成 Eval Preview

新增脚本：

```text
app/scripts/run_interview_eval_preview.py
```

输出：

```text
artifacts/eval/eval_score_table.csv
artifacts/eval/eval_summary.md
```

评分维度：

```text
能力缺口聚焦
证据约束
追问深度
岗位贴合
格式稳定
可用于报告
```

命令：

```bash
python -m app.scripts.run_interview_eval_preview --trace artifacts/agent_trace/python_backend.trace.json --out artifacts/eval
```

---

### 任务 P1-4：生成 SFT Preview

新增脚本：

```text
app/scripts/build_sft_preview.py
```

输出：

```text
artifacts/sft_preview/train.preview.jsonl
artifacts/sft_preview/validation.preview.jsonl
artifacts/sft_preview/summary.preview.json
```

命令：

```bash
python -m app.scripts.build_sft_preview --input demo_cases --out artifacts/sft_preview
```

要求：

```text
文件名必须含 preview。
summary 中区分 demo_constructed、real_authorized、constructed。
演示样本不得标记为真实训练样本。
```

---

## P2：后端最小服务化

新增：

```text
app/services/agent_orchestrator/__init__.py
app/services/agent_orchestrator/schemas.py
app/services/agent_orchestrator/registry.py
app/services/agent_orchestrator/orchestrator.py
app/services/agent_orchestrator/trace_logger.py
app/services/agent_orchestrator/demo_pipeline.py
```

### schemas.py 至少包含

```text
AgentStep
AgentTrace
EvidenceItem
RoleAbility
GapItem
InterviewQuestion
EvalScore
SFTPreviewRecord
```

### orchestrator.py 最小功能

```text
run_demo_pipeline(case_id) -> AgentTrace
```

### trace_logger.py 最小功能

```text
save_trace(trace, out_dir)
load_trace(trace_id)
export_markdown(trace)
```

---

## P3：前端和后台展示

### 用户端新增技术展示入口

页面建议：

```text
Career-AgentOS 技术展示
```

展示：

```text
目标岗位
简历证据链
能力缺口矩阵
AI 追问
报告摘要
Eval 分数
```

### 后台新增样本闭环展示

展示：

```text
样本来源
授权状态
人工评分
是否进入 eval
是否进入 SFT preview
```

如果时间不够，先只做静态页面或 Markdown 下载入口。

---

## P4：三个月补实任务

```text
1. 补真实授权样本。
2. 完成 OpenAI SFT job。
3. 完成 holdout eval。
4. 生成 DPO chosen/rejected 偏好数据。
5. 尝试 QLoRA 开源模型训练。
6. 输出成本、效果和可控性对比。
```

---

## 最终验收清单

```text
[ ] docs/competition 文档齐全
[ ] docs/agents 角色文档齐全
[ ] demo_cases 三岗位案例存在
[ ] Agent Trace 可导出
[ ] Eval Preview 可导出
[ ] SFT Preview 可导出
[ ] 前端或后台能展示至少一个 trace
[ ] PPT 页面大纲完成
[ ] 评委问答库完成
[ ] 三个月补实路线完成
```
