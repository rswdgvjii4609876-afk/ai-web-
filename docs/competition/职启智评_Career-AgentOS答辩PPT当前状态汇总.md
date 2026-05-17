# 职启智评 Career-AgentOS 答辩 PPT 当前状态汇总

生成时间：2026-05-17 19:27:16

## 1. 本次输出

- PPT：`docs/competition/申报书/final/职启智评_Career-AgentOS人工智能创新赛答辩PPT_正式版.pptx`
- 预览目录：`docs/competition/申报书/final/ppt_preview_careeros/`
- 状态汇总：`docs/competition/职启智评_Career-AgentOS答辩PPT当前状态汇总.md`

## 2. 当前 Git 状态

生成前仓库状态：

```text
## main...origin/main [ahead 2]
```

最近提交：

```text
78adf0d fix: harden review-driven workflow quality
924fbf7 fix: harden full-chain workflow gates
3f0633e fix: deepen competition workflow validation
```

说明：PPT 生成前本地 `main` 领先 `origin/main` 2 个提交；本次 PPT 和状态汇总如果提交，会新增一个本地提交。服务器要拿到这些内容，需要后续执行 `git push` 和服务器 `git pull`。

## 3. 当前真实能力

- 阶段 159-164 已完成代码级收口，重点包括 RAG/岗位知识库证据边界、隐私授权有效期、SFT 门禁、Competition Preview 严谨化、Celery/部署验收脚本增强。
- Career-AgentOS Preview 已具备三岗位 demo、Agent Trace、Eval Preview、SFT Preview 和用户端展示页。
- 简历润色 Agent 已被纳入答辩主线，口径为“岗位化表达 + 证据约束 + 风险提示”，不能编造经历。
- 本地验证口径：后端 pytest `193 passed, 1 skipped`；前端/后台 build 通过；`generate_competition_assets` 通过；SFT dry-run 因真实授权样本不足而拒绝创建 job，这是预期门禁。

## 4. 当前可展示能力

- `/competition/agent-trace` 可展示三岗位沙盘：Python 后端、产品助理、人力资源专员。
- Agent Trace 覆盖：简历证据、岗位画像、能力差距、简历润色、面试追问、报告、学习任务、数据治理、Eval Preview、SFT Preview。
- Eval Preview 使用七维 35 分：`baseline_prompt_preview=19/35`，`agent_optimized=34/35`。
- SFT Preview 当前统计：`demo_constructed=3`、`real_authorized=0`、`train_preview_records=6`、`ready_for_real_training=false`。

## 5. 不能夸大的边界

- 不能说 C1/C2/C3 已完成真实跑测、后台人工评分和记录回填。
- 不能说已完成真实 OpenAI SFT。
- 不能说已有 `官方微调模型 ID`。
- 不能把构造样本说成真实用户数据。
- 不能把 Eval Preview 写成真实 holdout eval 或真实模型实测。
- 不能说数据完全匿名化，只能说去标识化/脱敏。

## 6. 下一步建议

1. 推送当前本地提交，服务器拉取最新版本。
2. 在服务器重新执行部署验收：`bash scripts/stage138_server_closed_loop_verify.sh --deploy --allow-reset --readiness-only`。
3. 录制 3-5 分钟作品演示视频，替换 PPT 第 6 页占位。
4. 补 C1/C2/C3 真实授权样本、后台人工评分和 CSV 回填。
5. 当真实授权样本和 validation 样本达标后，再启动真实 OpenAI SFT job，并用 holdout eval 更新 PPT。
