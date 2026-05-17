# OPC 一人项目作战手册

OPC 在这里定义为：

```text
One-Person Command Center：一人总控中心。
```

你现在是一人项目，不适合搭一个复杂组织，但可以用 Agent 把自己拆成一个虚拟团队。

---

## 1. 一人 OPC 的核心原则

你本人只做三件事：

```text
1. 定方向：决定比赛主线、技术叙事、优先级。
2. 做取舍：哪些必须做，哪些只做演示，哪些三个月后补实。
3. 验收结果：检查 Codex 生成的代码、文档、PPT 是否能支撑答辩。
```

不要让自己陷入：

```text
每天修小 bug
反复重构
临时加大功能
追求真实完整训练链路
```

赛前目标不是完美系统，而是：

```text
稳定演示 + 强技术叙事 + 后续可补实。
```

---

## 2. OPC 虚拟团队结构

```text
你本人：OPC Commander
Codex：工程执行 Agent
ChatGPT：架构/答辩/文档 Agent
项目系统：业务执行 Agent
PPT：对评委展示的最终接口
```

推荐虚拟团队：

```text
1. Competition Story Agent：比赛叙事
2. Architecture Agent：架构设计
3. Backend Agent：后端改造
4. Frontend Agent：前端展示
5. Data Agent：演示样本和数据结构
6. Eval Agent：评分和对比
7. SFT Agent：微调 Preview 和路线
8. Defense Agent：评委问答
```

---

## 3. 每天工作流

每天不要乱改，按这个流程：

```text
早上：OPC Commander 确定当天唯一目标
上午：Codex 完成文档或代码任务
下午：跑一次演示或生成一次资产
晚上：Defense Agent 生成答辩话术和风险问题
```

每天都要有一个可以保存的产物：

```text
Markdown 文件
架构图
trace 文件
eval 表格
PPT 页面
演示视频
```

---

## 4. OPC 决策规则

遇到任何任务，先问四个问题：

```text
1. 这个东西能不能出现在 PPT 上？
2. 这个东西能不能让评委觉得技术更完整？
3. 这个东西会不会破坏现有演示稳定性？
4. 三个月内能不能补实？
```

如果答案是：

```text
能上 PPT + 能讲清楚 + 不破坏演示 + 后续能补实
```

就做。

如果是：

```text
只为了技术洁癖，PPT 看不见，且有风险
```

先不做。

---

## 5. OPC 赛前优先级

```text
P0：答辩主线、PPT、演示样本、Agent Trace、Eval 表、SFT Preview。
P1：后端最小 Agent Orchestrator、导出脚本、前端展示页。
P2：真实数据补充、OpenAI SFT job、自动化评估。
P3：DPO、QLoRA、本地开源模型部署。
```

---

## 6. OPC 任务看板

建议创建：

```text
docs/opc/今日任务.md
docs/opc/比赛前风险清单.md
docs/opc/Codex任务队列.md
docs/opc/已完成资产清单.md
docs/opc/答辩状态表.md
```

`答辩状态表.md` 可以这样写：

| 模块 | 当前状态 | PPT 表达 | 三个月补实 |
|---|---|---|---|
| 多 Agent 架构 | 设计完成/演示级 | 已完成 Career-AgentOS 设计 | 后端服务化 |
| SFT 数据链路 | Preview 完成 | 已完成 SFT-ready 链路 | 跑真实 job |
| Eval | 评分表完成 | 已建立评估体系 | 扩充 holdout |
| DPO | 路线设计 | 已规划偏好对齐 | 收集好坏样本 |
| QLoRA | 路线设计 | 已规划私有化降本方案 | 开源模型训练 |

---

## 7. 每次交给 Codex 的任务格式

```text
任务名称：
目标：
当前文件：
要新增/修改的文件：
不要动的文件：
验收标准：
可用于 PPT 的输出：
```

示例：

```text
任务名称：生成 Agent Trace 演示资产
目标：基于 demo_cases/python_backend.json 输出一次完整 Career-AgentOS 工作流 trace
要新增文件：app/scripts/export_agent_trace.py、artifacts/agent_trace/python_backend.md
不要动的文件：现有面试主流程 API
验收标准：命令可运行，输出包含简历证据、岗位画像、能力缺口、追问、报告摘要、Eval 评分
可用于 PPT：trace 截图、能力缺口表、追问对比
```
