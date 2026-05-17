# Career-AgentOS 答辩 PPT QA 报告

- 生成时间：`2026-05-17 19:34:40`
- PPT 文件：`docs/competition/申报书/final/职启智评_Career-AgentOS人工智能创新赛答辩PPT_正式版.pptx`
- PDF 文件：`docs/competition/申报书/final/ppt_preview_careeros/职启智评_Career-AgentOS人工智能创新赛答辩PPT_正式版.pdf`
- 逐页 PNG：`docs/competition/申报书/final/ppt_preview_careeros/slide-01.png` 至 `slide-19.png`
- Contact sheet：`docs/competition/申报书/final/ppt_preview_careeros/contact_sheet.png`

## 渲染检查

- Slide count：`19`
- PNG count：`19`
- 第 6 页视频占位检查：`PASS`
- 已检查 contact sheet 和关键页：封面、视频页、Eval、SFT、隐私治理页。
- Eval/SFT 长标题已二次修正，未发现明显文字重叠或中文乱码。

## 内容边界检查

- `已完成真实微调`：`PASS`
- `真实闭环已通过`：`PASS`
- `效果提升 xx%`：`PASS`
- `构造样本是真实用户`：`PASS`
- `fine_tuned_model`：`PASS`

## 必要口径检查

- `baseline 是规则基线`：`PASS`
- `不是真实模型实测`：`PASS`
- `ready_for_real_training`：`PASS`
- `for_training=false`：`PASS`
- `真实授权样本不足`：`PASS`

## 工具说明

- 已尝试 Presentations runtime，`@oai/artifact-tool` 链接失败；本次降级使用 `python-pptx` 生成可编辑 PPTX，并用 LibreOffice/Poppler 导出 PDF/PNG。
- Browser Use 的 node_repl 入口在当前工具集中不可用；本次使用本地渲染 PNG 与 contact sheet 完成视觉 QA。

## 后续建议

- 录制作品演示视频后替换第 6 页占位。
- 服务器部署最新提交后，可更新第 14 页部署验收状态。
- C1/C2/C3 真实跑测和真实 OpenAI SFT 完成后，再更新第 12/15/17 页边界口径。
