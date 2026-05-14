# 成员知识库入库使用检查报告

- 检查模式：package
- 岗位数量：7
- 已入库标准岗位画像数量：0
- 切片总数：72
- 问答经验启用切片数：22

## 岗位覆盖与切片质量

| 岗位 | 标准画像标题 | 入库状态 | 切片数 | 启用切片 | 问答经验切片 | 资料包面经数 | 备注 |
|---|---|---|---:|---:|---:|---:|---|
| 产品助理 | 职启智评岗位画像：产品助理 | 待归并入标准岗位画像 | 12 | 12 | 5 | 5 | package_ready_for_canonical_merge |
| 运营助理 | 职启智评岗位画像：运营助理 | 待归并入标准岗位画像 | 11 | 11 | 4 | 4 | package_ready_for_canonical_merge |
| 人力资源专员 | 职启智评岗位画像：人力资源专员 | 待归并入标准岗位画像 | 12 | 12 | 5 | 5 | package_ready_for_canonical_merge |
| Python后端开发工程师 | 职启智评岗位画像：Python后端开发工程师 | 待归并入标准岗位画像 | 12 | 12 | 4 | 4 | package_ready_for_canonical_merge |
| Java后端开发工程师 | 职启智评岗位画像：Java后端开发工程师 | 待归并入标准岗位画像 | 9 | 9 | 2 | 2 | package_ready_for_canonical_merge |
| 前端开发工程师 | 职启智评岗位画像：前端开发工程师 | 待归并入标准岗位画像 | 8 | 8 | 1 | 1 | package_ready_for_canonical_merge |
| 算法工程师 | 职启智评岗位画像：算法工程师 | 待归并入标准岗位画像 | 8 | 8 | 1 | 1 | package_ready_for_canonical_merge |

## 待补岗位

| 岗位 | 当前处理建议 |
|---|---|
| 测试工程师 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 数据分析师 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 新媒体运营 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 招聘助理 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |
| 行政管理助理 | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |

## 使用位置

- 公共岗位画像：成员资料应归并到已有标准岗位画像，而不是作为并列新画像。
- 问答经验：结构化面经通过 `source_section=interview_experience` 进入切片。
- RAG 追问：面试路由可检索岗位要求、问答经验、能力模型、面试追问切片。
- 简历润色：读取标准岗位画像作为岗位要求和表达优化参考，不把知识库内容写成候选人经历。
- 能力诊断/学习任务：岗位知识库只作为岗位标准，不作为候选人真实能力证据。

## 服务器验收命令

```bash
docker compose exec app python -m app.scripts.import_member_knowledge_packages --check-only
docker compose exec app python -m app.scripts.import_member_knowledge_packages --dry-run
docker compose exec app python -m app.scripts.import_member_knowledge_packages
docker compose exec app python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run
docker compose exec app python -m app.scripts.merge_member_supplement_knowledge_bases
docker compose exec app python -m app.scripts.check_member_knowledge_usage --database
```

## 风险提醒

- 旧的 `成员资料补充：{岗位}` 画像仅作为历史补充资料，不应长期出现在前台岗位选择或润色来源优先级中。
- 图片型 `面试经历.docx` 未进入本次入库包，必须 OCR 或人工转写后再提交。
- `仅参考` 和 `待核验` 资料可作为追问方向，不应作为候选人真实能力证据。
