# 成员知识库入库使用检查报告

- 检查模式：package
- 岗位数量：7
- 已入库岗位数量：0
- 切片总数：72
- 问答经验启用切片数：22

## 岗位覆盖与切片质量

| 岗位 | 画像标题 | 入库状态 | 切片数 | 启用切片 | 问答经验切片 | 资料包面经数 | 备注 |
|---|---|---|---:|---:|---:|---:|---|
| 产品助理 | 成员资料补充：产品助理 | 待正式入库 | 12 | 12 | 5 | 5 | package_ready |
| 运营助理 | 成员资料补充：运营助理 | 待正式入库 | 11 | 11 | 4 | 4 | package_ready |
| 人力资源专员 | 成员资料补充：人力资源专员 | 待正式入库 | 12 | 12 | 5 | 5 | package_ready |
| Python后端开发工程师 | 成员资料补充：Python后端开发工程师 | 待正式入库 | 12 | 12 | 4 | 4 | package_ready |
| Java后端开发工程师 | 成员资料补充：Java后端开发工程师 | 待正式入库 | 9 | 9 | 2 | 2 | package_ready |
| 前端开发工程师 | 成员资料补充：前端开发工程师 | 待正式入库 | 8 | 8 | 1 | 1 | package_ready |
| 算法工程师 | 成员资料补充：算法工程师 | 待正式入库 | 8 | 8 | 1 | 1 | package_ready |

## 待补岗位

| 岗位 | 当前处理建议 |
|---|---|
| 测试工程师 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 数据分析师 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 新媒体运营 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 招聘助理 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 行政管理助理 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |

## 使用位置

- 公共岗位画像：后台可查看 `成员资料补充：{岗位}`。
- RAG 追问：面试路由可检索岗位要求、问答经验、能力模型、面试追问切片。
- 简历润色：可读取同岗位公共知识库作为岗位要求和表达优化参考。
- 能力诊断/学习任务：只把岗位知识库作为岗位标准，不把它当作候选人真实经历。

## 服务器验收命令

```bash
docker compose exec app python -m app.scripts.import_member_knowledge_packages --check-only
docker compose exec app python -m app.scripts.import_member_knowledge_packages --dry-run
docker compose exec app python -m app.scripts.import_member_knowledge_packages
docker compose exec app python -m app.scripts.check_member_knowledge_usage --database
```

## 风险提醒

- 图片型 `面试经历.docx` 未进入本次入库包，必须 OCR 或人工转写后再提交。
- 本批资料是第一批成员资料补充，不覆盖原有公共岗位画像。
- `仅参考` 和 `待核验` 资料可作为追问方向，不应作为候选人真实能力证据。
