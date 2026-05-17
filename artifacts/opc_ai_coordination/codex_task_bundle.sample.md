# Codex Task Bundle Sample

## Objective

生成 OPC 参赛材料和 AI 协同工作流包。

## Inputs

- `PROJECT_MEMORY.md`
- `任务记录文档.md`
- `docs/competition/职启智评_OPC超级个体备赛包_2026-05-17/`

## Outputs

- `docs/competition/opc/`
- `docs/competition/opc_ai_coordination/`
- `artifacts/opc_ai_coordination/`
- 更新主控记忆文档。

## Constraints

- 不改业务代码。
- 不新增数据库表。
- 不宣称真实 OpenAI SFT 已完成。
- 不把 demo 样本说成真实用户数据。

## Acceptance

- 所有文件非空。
- `git diff --check` 通过。
- 风险词扫描通过。
