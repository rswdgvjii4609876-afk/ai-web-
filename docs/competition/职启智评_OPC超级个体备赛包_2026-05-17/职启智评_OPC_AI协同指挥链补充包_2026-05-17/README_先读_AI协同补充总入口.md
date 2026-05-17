# 职启智评 OPC：AI 协同指挥链补充包

用途：补强京彩大创 OPC 超级个体赛道中“AI 工作流构建能力、人机协同逻辑设计、AI 之间如何协作”的表达与工程落地。

## 为什么补这个包

之前材料更多讲“职启智评产品是什么、Career-AgentOS 有哪些 Agent”。但 OPC 评委还会看：

- 你本人如何使用 AI；
- 你先用哪个 AI、后用哪个 AI；
- ChatGPT、Codex、业务大模型、Eval/后台评分之间如何交接；
- 每类 prompt 的侧重点；
- 每段聊天记录如何转成 Codex 的具体操作和生成文件；
- 你如何验收 AI，而不是让 AI 自由发挥。

本包的核心结论：

> 我的能力不是“会用 AI 工具”，而是“能把多个 AI 编排成可复用、可追踪、可验收的轻量化创新单元”。

## Codex 阅读顺序

1. `README_先读_AI协同补充总入口.md`
2. `00_Codex总提示词_直接复制.md`
3. `01_OPC_AI协同总架构.md`
4. `02_我的AI使用顺序_从调研到落地.md`
5. `03_多AI角色分工与交接协议.md`
6. `04_ChatGPT提示词库_按阶段.md`
7. `05_Codex提示词库_按阶段.md`
8. `06_聊天记录到Codex任务映射表.md`
9. `07_一轮任务如何从聊天变成代码.md`
10. `08_复赛现场限时实测SOP.md`
11. `09_答辩讲法_AI之间如何协调.md`
12. `10_Codex生成文件清单.md`
13. `11_证据材料整理规范.md`
14. `12_任务记忆文档追加模板.md`
15. `13_评委追问_AI协同版.md`

## 本轮 Codex 目标

新建：

```text
docs/competition/opc_ai_coordination/
artifacts/opc_ai_coordination/
```

生成：

```text
AI协同总架构.md
AI使用顺序手册.md
Prompt模板库.md
聊天记录到任务映射表.md
Codex执行SOP.md
复赛限时实测SOP.md
答辩话术_AI协同版.md
AI协同证据材料清单.md
ai_workflow_trace.sample.json
ai_prompt_chain.sample.md
codex_task_bundle.sample.md
ai_handoff_log.sample.md
```

核心表达：

> 我先用 ChatGPT 做赛道判断和任务拆解，再让 ChatGPT 生成 Codex 任务包；Codex 读取项目记忆、按路径和验收标准落地代码/文档/脚本；产品内业务大模型负责简历、岗位、面试、报告生成；后台/Eval 负责评分校验；我本人负责总控、取舍和最终验收。
