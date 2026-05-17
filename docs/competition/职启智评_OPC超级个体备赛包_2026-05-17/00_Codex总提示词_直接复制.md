# Codex 总提示词：OPC 超级个体备赛适应性改造

你是 `D:\apps\ai-interview` 项目的 Codex 工程 Agent、赛事材料 Agent 和 OPC 工作流教练。当前任务不是重写项目，而是在不破坏现有 FastAPI / Vue / PostgreSQL / Docker Compose 主链路的前提下，把“职启智评”从传统 AI 产品叙事，升级为第五届“京彩大创”北京大学生“超级个体”（OPC）创业大赛可用的 AI 原生结构展示项目。

## 一、必须先阅读的项目文件

请先阅读这些文件，形成当前状态理解：

```text
PROJECT_MEMORY.md
任务记录文档.md
docs/competition/职启智评项目升级流程手册.md
docs/competition/职启智评_Career-AgentOS答辩PPT当前状态汇总.md
docs/competition/职启智评_AI原生结构说明书.docx 或其转写内容
```

如果路径不存在，先用 `find` 或 `rg` 搜索相近文件，不要凭空假设。

## 二、本轮总目标

把项目主线改成：

```text
职启智评 OPC：一个人 + AI Agents 构建高校就业能力诊断与训练服务单元
```

不要只讲“我做了 AI 面试平台”，要讲：

```text
我如何作为超级个体，设计 AI 工作流、人机协同结构、垂直行业嵌入和轻量化创新单元。
```

## 三、必须生成的 Markdown 文件

请在项目中新增：

```text
docs/competition/opc/
  README_OPC参赛总入口.md
  01_赛事适配判断.md
  02_OPC参赛主叙事.md
  03_AI工作流总图.md
  04_人机协同分工图.md
  05_复赛集中限时实测训练包.md
  06_答辩PPT_OPC版页面结构.md
  07_三分钟讲稿_OPC版.md
  08_八分钟讲稿_OPC版.md
  09_评委问答库_OPC版.md
  10_一人OPC日常运行手册.md
  11_三个月补实路线.md
  12_可展示成果与不能夸大边界.md
```

## 四、必须生成或补齐的 Agent 文档

请在 `docs/agents/` 下检查并补齐：

```text
00_OPC_Commander_Agent.md
01_Competition_Research_Agent.md
02_Codex_Engineering_Agent.md
03_Architecture_Review_Agent.md
04_Resume_Evidence_Agent.md
05_Role_Profile_RAG_Agent.md
06_Gap_Diagnosis_Agent.md
07_Resume_Polish_Agent.md
08_Interviewer_Agent.md
09_Learning_Plan_Agent.md
10_Report_Review_Agent.md
11_Data_Governance_Agent.md
12_Eval_Judge_Agent.md
13_SFT_Dataset_Agent.md
14_Defense_Coach_Agent.md
```

每个 Agent 文档至少包含：

```text
角色定位
输入
输出
人机边界
调用工具或项目模块
失败兜底
适合答辩展示的一句话
```

## 五、必须生成的复赛限时实测训练包

新增：

```text
docs/competition/opc/live_test_drills/
  drill_01_30分钟构建AI工作流.md
  drill_02_45分钟重构人机协同结构.md
  drill_03_60分钟垂直场景落地方案.md
  drill_评分表.md
  drill_我的标准作答模板.md
```

每个 drill 都要包括：

```text
题目
限时
输入材料
我作为 OPC 怎么拆解
我让哪些 AI Agent 工作
最终交付物
评分点
现场讲解话术
```

## 六、代码改造边界

本轮优先生成文档和演示资产。代码只做最小展示增强：

```text
1. 不新增复杂数据库表。
2. 不改真实用户主流程。
3. 不破坏已有 /competition/agent-trace 页面。
4. 不伪造真实 OpenAI fine_tuned_model。
5. 不把 demo_constructed 写成真实用户样本。
6. 可新增只读 API 或脚本，用于展示 OPC 工作流 trace。
```

## 七、推荐新增脚本

如当前项目已有类似脚本，优先复用；没有再新增：

```text
ai-interview-backend/app/scripts/generate_opc_assets.py
ai-interview-backend/app/scripts/generate_opc_live_test_pack.py
ai-interview-backend/app/scripts/export_opc_workflow_trace.py
```

这些脚本输出到：

```text
artifacts/opc/
  opc_workflow_trace.json
  opc_workflow_trace.md
  live_test_drills_summary.md
  ppt_opc_assets.md
```

## 八、答辩表达原则

可以强势表达：

```text
我构建了 AI 原生就业服务工作流。
我用多 Agent 分工替代了小型就业咨询团队中的资料整理、简历诊断、面试训练、报告复盘和标注沉淀工作。
项目已具备可运行原型、三岗位演示沙盘、Agent Trace、Eval Preview、SFT Preview 和后台标注链路。
```

不要写成：

```text
我已经完成真实 OpenAI 微调。
我已经拥有大规模真实训练数据。
构造样本来自真实用户。
我自研了底层大模型。
```

## 九、完成后必须更新任务记忆

本轮结束前，必须更新或新增一段阶段记录到：

```text
PROJECT_MEMORY.md
任务记录文档.md
docs/competition/职启智评项目升级流程手册.md
```

阶段标题建议：

```text
阶段 165：OPC 超级个体参赛叙事与 AI 工作流备赛包生成
```

记录必须包含：

```text
背景
本轮处理
新增文件
决策
验证
未完成事项
```

## 十、验收标准

本轮算完成，必须满足：

```text
1. docs/competition/opc/ 下有完整 OPC 参赛材料。
2. docs/agents/ 下能体现“一个人 + 多 AI Agent”的工作流结构。
3. 复赛集中限时实测训练包可直接拿来练。
4. PPT 主线已经从“AI 面试平台”改成“OPC 超级个体 AI 原生就业服务单元”。
5. 任务记忆文档追加完成。
6. 所有 preview/demo/constructed 样本仍保留明确标记。
```
