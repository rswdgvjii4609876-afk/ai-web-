# Codex 执行 SOP

## 1. 开始前

```powershell
cd D:\apps\ai-interview
git -c core.quotepath=false status -sb
```

必须确认本轮目标、相关文件和不提交范围。

## 2. 执行中

- 先读记忆文档。
- 只改本轮文件。
- 不碰 `.env`、真实简历、API Key、训练输出。
- 对文档和代码都执行边界检查。

## 3. 验证

```powershell
git diff --check
rg -n "真实训练已落地|官方微调模型 ID 已取得|真实闭环全部通过|构造样本来自真实用户" docs/competition/opc docs/competition/opc_ai_coordination
```

## 4. 提交

精准暂存，不使用 `git add .`。
