# 10 Codex 生成文件清单

## 文档文件

```text
docs/competition/opc_ai_coordination/README.md
docs/competition/opc_ai_coordination/AI协同总架构.md
docs/competition/opc_ai_coordination/AI使用顺序手册.md
docs/competition/opc_ai_coordination/Prompt模板库.md
docs/competition/opc_ai_coordination/聊天记录到任务映射表.md
docs/competition/opc_ai_coordination/Codex执行SOP.md
docs/competition/opc_ai_coordination/复赛限时实测SOP.md
docs/competition/opc_ai_coordination/答辩话术_AI协同版.md
docs/competition/opc_ai_coordination/AI协同证据材料清单.md
```

## 样例资产

```text
artifacts/opc_ai_coordination/ai_workflow_trace.sample.json
artifacts/opc_ai_coordination/ai_prompt_chain.sample.md
artifacts/opc_ai_coordination/codex_task_bundle.sample.md
artifacts/opc_ai_coordination/ai_handoff_log.sample.md
```

## 可选前端展示页

```text
ai-interview-frontend/src/views/competition/OpcAiWorkflow.vue
ai-interview-frontend/src/router/index.js
路由：/competition/opc-ai-workflow
```

## 必须更新

```text
PROJECT_MEMORY.md
任务记录文档.md
docs/competition/职启智评项目升级流程手册.md
```

## 验收标准

| 项目 | 通过标准 |
|---|---|
| AI 使用顺序 | 能说明先 ChatGPT、再 Codex、再业务大模型、最后 Eval/人工验收 |
| Prompt 模板 | 至少包含赛事分析、项目理解、AI协同、Codex任务、答辩转译五类 |
| 聊天到任务映射 | 至少 8 类聊天记录能映射到 Codex 文件/代码任务 |
| 样例资产 | JSON/MD 能展示 AI 交接过程 |
| 任务记忆 | 已追加阶段记录 |
| 不破坏主链路 | 不改核心生产接口，不新增大型依赖 |
