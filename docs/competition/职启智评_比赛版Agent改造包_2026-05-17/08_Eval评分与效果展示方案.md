# Eval 评分与效果展示方案

## 1. Eval 的比赛价值

评委最容易质疑：

```text
你怎么证明这个 AI 面试官更好？
```

所以必须准备 Eval，即使第一版是轻量版，也比只展示一个生成结果更可信。

Eval 的作用：

```text
1. 把“好不好”变成可评分维度。
2. 支撑 base prompt 和 Agent 优化版对比。
3. 支撑后续 SFT / DPO 的样本选择。
4. 让项目看起来像真实 AI 工程系统。
```

---

## 2. 对比对象

赛前建议先比较：

```text
Base Prompt：普通大模型提示词直接生成问题。
Agent Optimized：加入岗位画像、证据状态、能力缺口后的多 Agent 输出。
```

真实 SFT 完成后再比较：

```text
Base Model
Fine-tuned Model
Agent + Fine-tuned Model
```

---

## 3. 评分维度

每条问题按 1-5 分评分：

| 维度 | 高分标准 |
|---|---|
| 能力缺口聚焦 | 问题直接围绕能力缺口，不跑题 |
| 证据约束 | 不把岗位要求写成候选人经历，不编造经历 |
| 追问深度 | 要求候选人说明场景、任务、行动、结果、指标 |
| 润色可执行性 | 简历润色建议能落到真实经历、待补证据和风险提示 |
| 岗位贴合 | 符合目标岗位真实工作内容 |
| 格式稳定 | 输出结构清晰，可被后续系统解析 |
| 可用于报告 | 能帮助后续生成诊断报告和学习建议 |

总分：

```text
35 分满分
28 分以上：可展示为高质量 Agent 输出
21-27 分：可用但需优化
21 分以下：不建议进入样本池
```

---

## 4. Eval Score CSV 字段

```csv
case_id,target_role,model_variant,focus_score,evidence_score,depth_score,polish_score,role_fit_score,format_score,report_score,total_score,judge_note
```

示例：

```csv
demo_python_backend_001,Python后端,base_prompt,3,2,3,2,3,3,3,19,"问题较泛，缺少证据约束，润色容易泛化"
demo_python_backend_001,Python后端,agent_optimized,5,5,5,5,4,5,5,34,"围绕 Redis 缺失证据追问，润色边界清楚，适合进入报告闭环"
```

注意：如果是演示评分，文件名和 summary 中写清楚：

```text
preview / demo / 沙盘评估
```

---

## 5. Eval Summary 模板

```markdown
# Eval Preview Summary

## 样本范围

- 样本类型：demo_constructed
- 岗位覆盖：Python 后端、产品助理、人力资源
- 用途：比赛演示与评分流程验证

## 对比对象

- base_prompt：普通大模型直接生成
- agent_optimized：Career-AgentOS 加入岗位画像和证据链后的输出

## 观察结果

Agent 优化版在以下维度表现更稳定：

1. 能力缺口聚焦
2. 证据约束
3. 追问深度
4. 润色可执行性
5. 格式稳定

## 下一步

后续将把真实授权样本加入 holdout，完成 base model、fine-tuned model 和 agent optimized 的正式对比。
```

---

## 6. PPT 展示方式

可以用表格：

| 版本 | 能力聚焦 | 证据约束 | 追问深度 | 润色可执行性 | 格式稳定 | 总分 |
|---|---:|---:|---:|---:|---:|---:|
| 通用 Prompt | 3 | 2 | 3 | 2 | 3 | 19/35 |
| Career-AgentOS | 5 | 5 | 5 | 5 | 5 | 34/35 |

标题：

```text
沙盘评估：多 Agent 编排提升追问聚焦度、证据约束和润色可执行性
```

更稳妥的表述：

```text
在三岗位演示样例中，Career-AgentOS 相比普通 Prompt 展现出更强的能力缺口聚焦、证据约束和简历润色边界控制能力。
```

---

## 7. Eval 与 SFT/DPO 的关系

```text
Eval 高分样本 -> 可进入 SFT 正样本候选
Eval 低分样本 -> 可作为反例分析
同一问题的好/坏两个回答 -> 可进入 DPO 偏好数据
真实用户授权样本 + 人工评分 -> 正式训练和验证数据
```

这让 Eval 不只是展示，而是模型后训练的数据入口。

---

## 8. Codex 任务

请实现：

```text
app/scripts/run_interview_eval_preview.py
```

功能：

```text
1. 读取 artifacts/agent_trace/*.trace.json。
2. 按 6 个维度生成评分。
3. 输出 eval_score_table.csv。
4. 输出 eval_summary.md。
5. 标记评估类型为 preview/demo。
```

第一版可以使用规则评分，不强制调用大模型。

规则示例：

```text
如果问题包含目标能力词，加能力聚焦分。
如果问题明确提到“简历未体现/没有看到证据/仅写熟悉”，加证据约束分。
如果问题要求场景、行动、结果、指标，加追问深度分。
如果输出为 JSON 且字段完整，加格式稳定分。
```
