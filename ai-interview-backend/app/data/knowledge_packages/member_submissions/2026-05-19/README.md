# 2026-05-19 图片面试经验候选入库包

本目录保存从成员 DOCX 图片型面经中抽取、OCR/视觉转写并结构化后的候选入库包。

## 文件说明

- `source_images/`：DOCX 解包图片。
- `extracted_interview_experience.md`：图片引用、OCR 原文、清洗文本和候选问答。
- `member_interview_experience_package.json`：`knowledge_package_v1` 正式候选包。
- `member_interview_experience_preview.md`：人工预览。
- `extraction_manifest.json`：来源、hash、OCR 状态、岗位映射和审核状态。
- `ocr_overrides.json`：当本地 OCR 不可用或低置信时的人工视觉转写/复核覆盖。

## 入库命令

```bash
docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages --source /app/app/data/knowledge_packages/member_submissions/2026-05-19 --check-only
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages --source /app/app/data/knowledge_packages/member_submissions/2026-05-19 --dry-run
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages --source /app/app/data/knowledge_packages/member_submissions/2026-05-19
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases
docker compose exec -T app python -m app.scripts.check_member_knowledge_usage --source /app/app/data/knowledge_packages/member_submissions/2026-05-19 --database
docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict
```

## 边界

- 图片内容只作为岗位面经知识和追问方向，不是候选人真实经历。
- `不采用` 资料不生成启用切片。
- `待核验` 资料可作为追问方向，但需要人工复核。
