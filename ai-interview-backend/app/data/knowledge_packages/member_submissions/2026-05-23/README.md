# 2026-05-23 图片面试经验候选入库包

本目录保存从成员 DOCX 图片型面经中抽取、OCR/视觉转写并结构化后的候选入库包。

## 文件说明

- `source_images/`：DOCX 解包图片。
- `extracted_interview_experience.md`：图片引用、OCR 原文、清洗文本和候选问答。
- `new_images_review.md`：未按 hash 复用旧批次转写的新增图片复核清单。
- `member_interview_experience_package.json`：`knowledge_package_v1` 正式候选包。
- `member_interview_experience_preview.md`：人工预览。
- `extraction_manifest.json`：来源、hash、OCR 状态、岗位映射和审核状态。
- `ocr_overrides.json`：当本地 OCR 不可用或低置信时的人工视觉转写/复核覆盖。

## 入库命令

```bash
cd /opt/apps/ai-interview
./scripts/import_member_knowledge_server.sh --package-date 2026-05-23
./scripts/import_member_knowledge_server.sh --package-date 2026-05-23 --execute
./scripts/import_member_knowledge_server.sh --package-date 2026-05-23 --verify-only
```

日志路径：`ai-interview-backend/logs/member_knowledge_imports/20260523_<mode>_<timestamp>.log`。

## 边界

- 图片内容只作为岗位面经知识和追问方向，不是候选人真实经历。
- `不采用` 资料不生成启用切片。
- `待核验` 资料只保留在 Markdown/manifest，默认不进入正式 package；人工确认后再补入。
- `可入库` 可进入标准岗位画像；`仅参考` 可进入低优先级参考切片。
