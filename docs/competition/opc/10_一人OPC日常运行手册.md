# 10 一人 OPC 日常运行手册

## 1. 每日启动

1. 阅读 `PROJECT_MEMORY.md` 和 `任务记录文档.md`。
2. 明确今天只推进一个最高优先级目标。
3. 用 ChatGPT 做策略拆解和风险复核。
4. 用 Codex 落地文档、代码、测试或部署检查。
5. 由我本人决定是否提交、是否进入下一阶段。

## 2. 每轮任务 SOP

```text
目标输入 -> ChatGPT 策略拆解 -> Codex 执行计划 -> Codex 改造/生成 -> 测试/QA -> 人工验收 -> 任务记忆更新 -> 精准提交
```

## 3. 角色调用顺序

1. Competition Research Agent：判断赛事口径。
2. OPC Commander Agent：决定任务优先级。
3. Codex Engineering Agent：执行工程或文档落地。
4. Data Governance Agent：检查隐私、授权和样本边界。
5. Eval Judge Agent：检查输出质量。
6. Defense Coach Agent：转成答辩语言。

## 4. 不能做的事

- 不用 `git add .`。
- 不提交 API Key、`.env`、真实简历原文、未脱敏样本。
- 不把 preview/demo 说成真实训练结果。
- 不用岗位知识库编造候选人经历。
- 不在未授权情况下沉淀训练样本。

## 5. 每日收口

输出：

- 今日目标。
- AI 分工。
- 新增文件或代码。
- 验证命令。
- 风险边界。
- 下一步。
