# AI Prompt Chain Sample

## 1. Strategy Prompt to ChatGPT

```text
请基于 OPC 赛道要求和职启智评项目资料，判断评委看什么，并把项目重构为一人 + 多 AI Agents 的工作流。
```

## 2. Task Prompt to Codex

```text
请读取 PROJECT_MEMORY.md 和任务记录文档.md，在 docs/competition/opc_ai_coordination/ 生成 AI 协同总架构、AI 使用顺序、Prompt 模板库和聊天记录到任务映射表。
```

## 3. Validation Prompt to ChatGPT

```text
以下是 Codex 的文件清单和验证结果，请转成评委能听懂的 60 秒 AI 协同答辩话术。
```
