# 05 Codex 提示词库：按阶段

## 1. 资料对齐 Prompt

```text
你是 AI-Interview / 职启智评项目的 Codex 工程 Agent。
本轮先不改代码，只做项目状态理解。

请依次读取：
1. PROJECT_MEMORY.md
2. 任务记录文档.md
3. docs/competition/职启智评项目升级流程手册.md
4. docs/competition/职启智评_Career-AgentOS答辩PPT当前状态汇总.md

请输出：
- 当前项目真实能力清单
- 当前比赛展示能力清单
- 当前不能夸大的内容
- 与 OPC AI 协同有关的已有材料
- 建议新增的 docs/competition/opc_ai_coordination 文件结构

不要修改任何文件。
```

## 2. 生成 AI 协同文档 Prompt

```text
请在 docs/competition/opc_ai_coordination/ 下生成一套 OPC AI 协同材料。

必须包含：
README.md、AI协同总架构.md、AI使用顺序手册.md、Prompt模板库.md、
聊天记录到任务映射表.md、Codex执行SOP.md、复赛限时实测SOP.md、
答辩话术_AI协同版.md、AI协同证据材料清单.md。

内容重点：
- 我如何先用 ChatGPT 做赛道分析和任务拆解。
- 我如何再用 Codex 做代码、文档、脚本、测试和展示页。
- 业务大模型如何在产品内部运行。
- Eval/后台评分如何校验。
- 每一轮聊天记录如何变成 Codex 任务。

不要新增依赖，不要改生产主链路。
```

## 3. 生成样例资产 Prompt

```text
请在 artifacts/opc_ai_coordination/ 下生成：
1. ai_workflow_trace.sample.json
2. ai_prompt_chain.sample.md
3. codex_task_bundle.sample.md
4. ai_handoff_log.sample.md

要求：
- 全部标记为 sample/demo。
- 不包含真实 API Key、真实隐私、未授权样本。
- 内容服务 OPC 答辩。
```

## 4. 可选展示页 Prompt

```text
请检查用户端 competition 展示页面和路由结构。
如果不破坏现有页面，请新增只读展示页 /competition/opc-ai-workflow。

页面展示：
OPC 总控者、ChatGPT 策略 AI、Codex 工程 AI、业务大模型、Eval/后台评分、输出资产、验收闭环。

要求：
- 只读页面。
- 不调用真实训练接口。
- 不破坏 /competition/agent-trace。
- 若无法构建，说明原因。
```

## 5. 任务记忆更新 Prompt

```text
请在 PROJECT_MEMORY.md、任务记录文档.md、docs/competition/职启智评项目升级流程手册.md 追加本阶段记录。

阶段名称：阶段 165：OPC AI 协同指挥链材料与展示资产补齐。

记录必须包含：
用户输入摘要、本轮处理结果摘要、新增决策、待解决问题、修改文件与验证情况。
```
