# 06 聊天记录到 Codex 任务映射表

## 1. 总表

| 聊天记录类型 | 你对 ChatGPT 的输入 | ChatGPT 应输出 | 转给 Codex 的任务 | Codex 生成什么 |
|---|---|---|---|---|
| 赛事规则分析 | 官网原文、赛道说明、评委关注点 | 赛道适配、叙事方向、风险点 | 生成 OPC 参赛主线文档 | `docs/competition/opc/参赛主线.md` |
| 项目状态分析 | 任务记录、项目记忆、PPT 状态 | 当前能力、缺口、不能夸大项 | 更新项目状态和答辩口径 | `当前状态.md`、`答辩边界.md` |
| 技术路线设计 | 微调资料、Agent 设想 | SFT/RAG/Agent 技术取舍 | 生成技术路线和脚本任务 | `微调路线.md`、`sft_preview` 脚本 |
| AI 协同设计 | 你如何使用 AI、先后顺序 | AI 协同架构、Prompt 链 | 生成 AI 协同文档和展示页 | `opc_ai_coordination/*` |
| 答辩材料生成 | 比赛要求、项目亮点 | PPT 大纲、讲稿、问答库 | 生成 docs/competition 材料 | `PPT页面大纲.md`、`答辩稿.md` |
| 代码修复排错 | 具体报错、日志、环境 | 根因判断、修复策略 | 修改后端/前端/部署脚本 | 代码 patch、测试记录 |
| 功能升级 | 新功能目标和边界 | 模块设计、数据结构、验收标准 | 新增接口、页面、迁移、测试 | FastAPI/Vue/Alembic 变更 |
| 赛前演示 | 演示目标、三岗位案例 | 演示脚本、Trace、Eval 方案 | 生成 demo cases 和 artifacts | `demo_cases/`、`artifacts/` |
| 复赛实测训练 | 现场限时任务 | 拆解模板、现场 SOP | 生成 live test drill 文件 | `live_test_drills/` |

## 2. 例子：本轮缺口如何转成 Codex 任务

你指出：

```text
你没有注重 AI 之间的协调，比如我是怎么使用这个 AI，并且我会先怎么使用，后怎么使用，给出的 prompt 有什么侧重点，每个聊天记录又是具体让 Codex 怎么操作怎么生成的。
```

ChatGPT 应拆成：

```text
补齐 AI 协同指挥链：
1. AI 使用顺序
2. 多 AI 角色分工
3. Prompt 模板库
4. 聊天记录到 Codex 任务映射
5. Codex 执行 SOP
6. 现场限时实测 SOP
```

Codex 应执行：

```text
新增 docs/competition/opc_ai_coordination/*.md
新增 artifacts/opc_ai_coordination/*.sample.json / *.sample.md
可选新增 /competition/opc-ai-workflow 展示页
追加阶段 165 任务记录
```

答辩转译：

```text
我的优势不是会问 AI，而是能把 AI 对话变成工程任务、展示资产、验证记录和长期项目记忆。
```
