# 00_Codex 总提示词：补齐 OPC AI 协同指挥链

下面内容可以直接复制给 Codex。

```text
你是职启智评项目的 Codex 工程 Agent。当前任务不是新增复杂业务功能，而是补齐京彩大创 OPC 超级个体赛道最关键的“AI 协同指挥链”材料与可展示资产。

项目目录：D:\apps\ai-interview
项目名：AI-Interview / 职启智评
参赛定位：OPC 超级个体，一人 + 多 AI Agents 的高校就业能力诊断与训练服务单元。

你必须先阅读并遵守：
1. PROJECT_MEMORY.md
2. 任务记录文档.md
3. docs/competition/职启智评项目升级流程手册.md
4. 本补充包中的所有 Markdown

本轮目标：
把“我作为一个人如何使用多个 AI 协作推进项目”变成可读、可展示、可复盘的材料和最小展示资产。

重点不是再讲产品功能，而是讲：
- 我先如何用 ChatGPT 分析比赛规则、定位赛道和拆解评委关注点；
- 再如何把 ChatGPT 的战略结论转成 Codex 可执行任务；
- Codex 如何按任务记忆、项目约束、文件路径和验收标准进行工程改造；
- 业务大模型如何在产品内部承担简历解析、岗位匹配、面试追问、报告生成；
- Eval/后台评分如何检查 AI 输出质量；
- 最后由我本人进行总控、验收、取舍和答辩表达。

请执行以下任务：

【P0 文档资产】
1. 新建目录 docs/competition/opc_ai_coordination/
2. 生成以下文件：
   - README.md
   - AI协同总架构.md
   - AI使用顺序手册.md
   - Prompt模板库.md
   - 聊天记录到任务映射表.md
   - Codex执行SOP.md
   - 复赛限时实测SOP.md
   - 答辩话术_AI协同版.md
   - AI协同证据材料清单.md

【P0 样例资产】
3. 新建目录 artifacts/opc_ai_coordination/
4. 生成以下样例：
   - ai_workflow_trace.sample.json
   - ai_prompt_chain.sample.md
   - codex_task_bundle.sample.md
   - ai_handoff_log.sample.md

【P1 可选展示页】
5. 如果当前前端 competition 展示页结构清晰，则新增只读展示页 /competition/opc-ai-workflow。
6. 页面展示：OPC 总控者、ChatGPT 策略 AI、Codex 工程 AI、业务大模型、Eval/后台评分、人类验收之间的工作流。
7. 不允许破坏现有 /competition/agent-trace 页面。

【P1 任务记忆更新】
8. 在 PROJECT_MEMORY.md、任务记录文档.md、docs/competition/职启智评项目升级流程手册.md 中追加本阶段记录。
9. 阶段名称建议为：阶段 165：OPC AI 协同指挥链材料与展示资产补齐。

【硬性要求】
- 不要改动生产主链路。
- 不要新增大型依赖。
- 不要把构造样本说成真实用户数据。
- 不要宣称已经完成真实 OpenAI SFT。
- 不要删除已有 Career-AgentOS Preview、Agent Trace、Eval Preview、SFT Preview。
- 所有文档必须强调“AI 之间如何协作”和“我如何指挥 AI”。
- 所有新增内容要能服务复赛集中限时实测：现场拿到任务后，我能快速用 ChatGPT 拆解，再交给 Codex 生成任务包，再由我验收。

【最终输出】
请列出：
1. 新增/修改文件清单。
2. 每个文件的作用。
3. 是否运行测试/构建。
4. 未完成验证事项。
5. 下一步建议。
```
