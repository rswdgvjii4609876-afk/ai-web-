# AI Prompt Chain Sample

## 1. ChatGPT 策略 Prompt

```text
请根据 OPC 赛事通知和职启智评项目状态，生成 OPC 参赛主叙事、评委问答和 Codex 执行任务包。
```

## 2. Codex 执行 Prompt

```text
请在 D:\apps\ai-interview 中新增 docs/competition/opc，并生成 OPC 参赛材料。只提交本轮文件，不使用 git add .
```

## 3. 业务大模型 Prompt

```text
请根据岗位画像和候选人证据状态生成面试追问。不得把岗位知识库写成候选人真实经历。
```

## 4. Eval Prompt

```text
请检查输出是否满足证据约束、岗位贴合、隐私合规和样本准入。
```
