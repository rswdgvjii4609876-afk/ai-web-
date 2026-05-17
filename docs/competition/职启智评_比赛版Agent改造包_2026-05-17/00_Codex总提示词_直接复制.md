# Codex 总提示词：比赛版 Career-AgentOS 适应性改造

你是职启智评项目的 Codex 工程 Agent。当前目标不是重写项目，也不是盲目新增复杂功能，而是在已有项目基础上完成“比赛版多智能体就业能力诊断架构”的适应性改造。

## 1. 项目背景

项目名称：职启智评
原定位：就业能力诊断与提升平台 / AI 面试官
比赛定位升级：基于 Career-AgentOS 的多智能体就业能力诊断与训练平台

现有技术栈：

```text
前端用户端：Vue
后台管理端：Vue
后端：FastAPI
数据库：PostgreSQL
缓存与异步任务：Redis / Celery
部署：Docker Compose
大模型接入：OpenAI-compatible API
微调方向：OpenAI SFT 为第一阶段，DPO / QLoRA 为后续扩展路线
```

## 2. 改造目标

请完成一套“能让评委看懂并认可技术创新”的工程和文档资产：

```text
1. 把项目从单一 AI 面试官包装升级为多 Agent 就业诊断系统。
2. 新增文档型 Agent 角色体系。
3. 新增演示沙盘样本和 Agent Trace 导出。
4. 新增 Eval 评分表和展示材料。
5. 新增 SFT Preview，体现微调数据准备能力。
6. 新增 PPT 答辩材料和评委 Q&A。
7. 为三个月内补实真实 SFT / DPO / QLoRA 留好工程入口。
```

## 3. 必须新增的目录

```text
docs/
  competition/
  agents/
  eval/
  sft/
  opc/
  roadmaps/

scripts/ 或 app/scripts/
  generate_demo_cases.py
  export_agent_trace.py
  run_interview_eval_preview.py
  build_sft_preview.py
  generate_competition_assets.py

app/services/agent_orchestrator/
  __init__.py
  schemas.py
  registry.py
  orchestrator.py
  trace_logger.py
  demo_pipeline.py
```

如果当前项目结构不允许直接新增 `scripts/`，则优先放入 `app/scripts/`，保持和现有脚本风格一致。

## 4. 不要破坏的内容

```text
不要破坏现有登录、简历上传、能力诊断、模拟面试、报告生成主流程。
不要删除已有 OpenAI SFT 准备脚本。
不要改动 .env 中的真实 Key。
不要引入大型依赖导致 Docker build 失败。
不要把演示样本标记为真实授权训练样本。
```

## 5. 赛前优先级

优先级从高到低：

```text
P0：文档、PPT、演示 trace、沙盘样本、Eval 表格、SFT Preview。
P1：后端 Agent Orchestrator 最小可运行模块。
P2：前端技术展示页和后台样本闭环展示。
P3：真实 OpenAI SFT job、DPO、QLoRA、本地模型服务。
```

## 6. 可使用的答辩表达

在文档和 PPT 中优先使用：

```text
已完成 Career-AgentOS 多智能体就业诊断架构设计。
已完成就业诊断场景的后训练技术路线设计。
已完成面试追问生成任务的 SFT-ready 数据结构与 Preview 链路。
已完成三岗位沙盘案例和 Agent Trace 演示闭环。
已完成 Eval Judge 评分维度设计，可用于 base / optimized 对比。
```

不要在代码或文档里伪造：

```text
不存在的 fine_tuned_model。
不存在的 OpenAI job id。
不存在的真实样本规模。
没有来源的固定提升百分比。
```

## 7. 第一批验收标准

完成后应能看到：

```text
1. docs/competition/PPT页面大纲.md
2. docs/agents/ 下至少 10 个 Agent 角色文件
3. demo_cases/ 下至少 3 个 demo case
4. artifacts/agent_trace/ 下可读的 trace markdown
5. artifacts/eval/ 下 eval_score_table.csv 和 eval_summary.md
6. artifacts/sft_preview/ 下 train.preview.jsonl、validation.preview.jsonl、summary.preview.json
7. docs/competition/评委问答库.md
8. docs/competition/通俗手册_原项目改了什么创新点在哪.md
```

## 8. 开发方式

先生成文件和演示资产，再接入真实后端服务。所有脚本要支持 demo mode：

```bash
python -m app.scripts.generate_demo_cases --out demo_cases
python -m app.scripts.export_agent_trace --case python_backend --out artifacts/agent_trace
python -m app.scripts.run_interview_eval_preview --input artifacts/agent_trace --out artifacts/eval
python -m app.scripts.build_sft_preview --input demo_cases --out artifacts/sft_preview
```

如果项目已有不同命名规范，请自动适配，但输出文件名要保持可读。
