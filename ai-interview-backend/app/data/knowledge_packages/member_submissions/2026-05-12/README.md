# 2026-05-12 成员资料候选入库包

本目录是后端可部署的数据区，用于存放已经完成预检整理、准备导入公共岗位画像库的成员资料包。

## 数据来源

- 技术岗原始资料：`docs/competition/成员资料/02_技术岗岗位资料与面经负责人/待检查/2026-5-12/职启智评1～6(1).docx`
- 非技术岗原始资料：`docs/competition/成员资料/03_非技术岗岗位资料与面经负责人/待检查/2026-5-12/岗位画像.docx`
- 图片型面经：`docs/competition/成员资料/03_非技术岗岗位资料与面经负责人/待检查/2026-5-12/面试经历.docx`，当前只保留为待 OCR/人工转写资料，不进入本目录。

## 文件说明

- `tech_knowledge_package.json`：技术岗候选入库包，覆盖 Python 后端、Java 后端、前端、算法。
- `nontech_knowledge_package.json`：非技术岗候选入库包，覆盖产品助理、运营助理、人力资源专员。
- `tech_knowledge_package_preview.md`：技术岗 Markdown 预览。
- `nontech_knowledge_package_preview.md`：非技术岗 Markdown 预览。

## 入库方式

在后端目录执行：

```powershell
python -m app.scripts.import_member_knowledge_packages --check-only
python -m app.scripts.import_member_knowledge_packages --dry-run
python -m app.scripts.import_member_knowledge_packages
```

服务器 Docker 环境执行：

```bash
docker compose exec app python -m app.scripts.import_member_knowledge_packages --check-only
docker compose exec app python -m app.scripts.import_member_knowledge_packages --dry-run
docker compose exec app python -m app.scripts.import_member_knowledge_packages
```

脚本会把资料导入为公共岗位画像，标题格式为 `成员资料补充：{岗位}`，并自动重建知识切片。

## 使用边界

- 本目录保存的是整理后的候选数据，不保存原始大文件。
- 原始资料和来源留痕仍以 `docs/competition/成员资料/` 为准。
- `不采用` 的结构化面经不得作为启用切片使用。
- 岗位知识库只用于校准问题方向和岗位要求，不等于候选人真实经历。
