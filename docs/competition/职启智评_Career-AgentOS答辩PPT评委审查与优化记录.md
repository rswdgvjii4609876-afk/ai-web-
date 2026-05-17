# 职启智评 Career-AgentOS 答辩 PPT 评委审查与优化记录

生成时间：2026-05-17

## 1. 本次输出

- 新增 PPT：`docs/competition/申报书/final/职启智评_Career-AgentOS人工智能创新赛答辩PPT_评委优化版.pptx`
- 新增预览目录：`docs/competition/申报书/final/ppt_preview_careeros_judge_optimized/`
- 保留旧正式版：`docs/competition/申报书/final/职启智评_Career-AgentOS人工智能创新赛答辩PPT_正式版.pptx`

## 2. 评委审查结论

子 agent 以“比赛评委 + AI 产品经理 + LLM 工程评审”视角做只读审查，结论是：原正式版没有直接越界宣称“已完成真实 OpenAI SFT / 已有 fine_tuned_model / C1-C3 已通过 / demo 是真实用户”的硬伤，但存在影响评委第一眼信任和现场观感的问题。

主要优先级：

1. 视频页仍是占位，需要更专业的演示脚本区。
2. Eval Preview 的 `34/35` 容易被误解为真实模型效果，需要改成规则评分示例。
3. SFT Preview 的长 JSON 有视觉破损，需要改成结构化门禁说明。
4. 工程完成度页需要明确“本地已验收，服务器待复验”。
5. 背景痛点页需要消除断句和项目符号拥挤。

## 3. 已完成优化

- 封面三枚标签改为“证据约束 / 多 Agent / 数据闭环”，将安全边界放在页脚。
- 背景痛点页重写为“岗位看不清 / 证据说不清 / 训练沉不下”。
- Career-AgentOS 架构页按四层分组：诊断层、生成层、治理层、评测/后训练层。
- 视频页改为可替换 16:9 占位，并写入 3-5 分钟录屏脚本。
- Agent Trace 页改为基于 `artifacts/agent_trace` 的可视化面板，明确 demo/preview 边界。
- Eval Preview 页改为“一例七维拆解 + 三岗位汇总”，并明确不是真实 holdout eval 或真实模型实测。
- SFT Preview 页改为 `messages / metadata / gate` 三段式结构，突出 `ready_for_real_training=false` 是门禁有效。
- 工程完成度页改为“本地代码级收口，服务器待复验”。

## 4. 当前仍需后续补齐

- 录制 3-5 分钟作品演示视频，并替换第 6 页占位。
- 推送本地提交后，服务器拉取最新版本并重新执行部署验收。
- 补 C1/C2/C3 真实授权样本、后台人工评分和 CSV 回填。
- 当真实授权样本和 validation 样本达标后，再启动真实 OpenAI SFT job，并用 holdout eval 更新 PPT。

## 5. 答辩口径边界

可以说：

- 已完成 Career-AgentOS Preview、Agent Trace、Eval Preview、SFT-ready 工程门禁。
- 已完成证据约束简历润色、证据追问型面试和数据治理 fail-closed 的展示闭环。
- 当前 Eval 是 Preview 规则评分，用于说明评估方法。

不能说：

- 已完成真实 OpenAI SFT。
- 已有 `fine_tuned_model` 或官方微调模型 ID。
- C1/C2/C3 真实闭环已通过。
- demo_constructed 是真实用户数据。
- Eval Preview 是真实 holdout eval 或真实模型实测。
