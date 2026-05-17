# AI 协同总架构

## 1. 总定位

```text
我作为 OPC Commander，把 ChatGPT、Codex、业务大模型、Eval/后台评分组织成一条 AI 协同生产线。
```

## 2. 架构

```mermaid
flowchart TD
    H[我：OPC Commander] --> A[ChatGPT 策略 AI]
    A --> B[Codex 工程 AI]
    B --> C[业务大模型 Agent]
    C --> D[Eval/后台评分]
    D --> H

    A --> A1[赛道分析 / Prompt / Codex 任务包 / 答辩稿]
    B --> B1[代码 / 脚本 / 测试 / 部署 / 文档]
    C --> C1[简历解析 / 岗位画像 / 面试追问 / 报告]
    D --> D1[评分 / 人工复核 / 样本准入 / 风险发现]
```

## 3. 创新点

- AI 之间有上下游，不是混用工具。
- Prompt 被拆成战略 Prompt、工程 Prompt、业务 Prompt 和评估 Prompt。
- 聊天记录会沉淀为 Codex 任务、Markdown、脚本、页面、测试和任务记忆。
- 人保留最终责任，AI 不替代真实性和合规判断。
