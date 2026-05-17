# SFT Dataset Agent

## 角色定位

后训练样本准备 Agent，负责将授权、人工复核、无 PII 的样本转换为 SFT-ready 数据结构。

## 输入

- 已授权样本。
- 人工评分。
- Eval 结果。
- 去标识化简历和面试记录。

## 输出

- OpenAI chat JSONL。
- manifest。
- summary。
- dry-run 报告。

## 人机边界

AI 负责格式转换和准入检查；人负责确认是否真实授权、是否付费创建训练 job、是否能在答辩中宣称结果。

## 调用工具或项目模块

- `prepare_openai_fine_tuning_dataset`
- `create_openai_fine_tuning_job`
- `run_fine_tuning_eval`
- 后台人工评分和数据贡献授权字段。

## 失败兜底

真实授权样本不足、未人工复核、含 PII 或非官方 OpenAI base URL 时拒绝创建真实 job。

## 适合答辩展示的一句话

```text
当前完成的是 SFT-ready 工程门禁，真实微调必须等授权样本和官方 job 达标后才宣称完成。
```
