# 2026-05-22 非技术岗资料与图片面经候选入库包

本目录保存从 `D:\apps\ai-interview_archive\2026-05-22` 抽取整理的非技术岗资料。文本 DOCX 生成结构化岗位画像补充，图片 DOCX 全量解包到 `source_images/` 并在 manifest 中留痕。

## 文件说明

- `source_images/`：从图片型 DOCX 解包出的 62 张图片。
- `extracted_interview_experience.md`：原 DOCX 正文、图片引用、OCR/视觉转写结果。
- `ocr_overrides.json`：复用 2026-05-19 同 hash 图片的人工视觉转写。
- `member_interview_experience_package.json`：`knowledge_package_v1` 正式候选入库包。
- `member_interview_experience_preview.md`：人工预览。
- `extraction_manifest.json`：来源、hash、OCR 状态、岗位映射和审核状态。

## 服务器导入命令

推荐先使用仓库根目录的一键脚本：

```bash
cd /opt/apps/ai-interview
scripts/import_20260522_member_knowledge_server.sh
scripts/import_20260522_member_knowledge_server.sh --execute
scripts/import_20260522_member_knowledge_server.sh --verify-only
```

如需手工分步执行，可使用下面命令：

```bash
cd /opt/apps/ai-interview
git pull
docker compose up -d --build
docker compose exec -T app alembic upgrade head

docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync

docker compose exec -T app python -m app.scripts.import_member_knowledge_packages   --source /app/app/data/knowledge_packages/member_submissions/2026-05-22   --check-only

docker compose exec -T app python -m app.scripts.import_member_knowledge_packages   --source /app/app/data/knowledge_packages/member_submissions/2026-05-22   --dry-run   --create-missing-canonical   --activate-created-canonical

docker compose exec -T app python -m app.scripts.import_member_knowledge_packages   --source /app/app/data/knowledge_packages/member_submissions/2026-05-22   --create-missing-canonical   --activate-created-canonical

docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases

docker compose exec -T app python -m app.scripts.check_member_knowledge_usage   --source /app/app/data/knowledge_packages/member_submissions/2026-05-22   --database

docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict
```

执行成功后验收：

- `active_member_supplements = 0`
- `产品助理 / 运营助理 / 新媒体运营 / 人力资源专员 / 招聘助理 / 行政管理助理` 的标准岗位画像为 active。
- 上述岗位存在 enabled `interview_experience` 切片。
- 后续可重复运行 `scripts/import_20260522_member_knowledge_server.sh --verify-only` 复查数据库状态。
- 每次脚本执行都会写入 `ai-interview-backend/logs/member_knowledge_imports/20260522_<mode>_<timestamp>.log`，可用于回看导入与验收输出。

## 边界

- 本包内容只作为岗位画像、RAG 检索知识、面试追问方向和学习材料。
- 图片内容不作为候选人真实经历。
- `--activate-created-canonical` 仅用于服务器缺少新岗位标准画像时直接创建标准公共画像；若已有多 active 标准画像，脚本仍会中止并要求人工处理。
