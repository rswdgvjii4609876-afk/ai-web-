# Career-AgentOS 答辩 PPT 评委优化版 QA 报告

- 生成时间：`2026-05-17`
- PPT 文件：`docs/competition/申报书/final/职启智评_Career-AgentOS人工智能创新赛答辩PPT_评委优化版.pptx`
- PDF 文件：`docs/competition/申报书/final/ppt_preview_careeros_judge_optimized/职启智评_Career-AgentOS人工智能创新赛答辩PPT_评委优化版.pdf`
- 逐页 PNG：`docs/competition/申报书/final/ppt_preview_careeros_judge_optimized/slide-01.png` 至 `slide-19.png`
- Contact sheet：`docs/competition/申报书/final/ppt_preview_careeros_judge_optimized/contact_sheet.png`

## 渲染检查

- Slide count：`19`
- PNG count：`19`
- 第 6 页视频占位：`PASS`
- 已检查 contact sheet 和关键页：第 2、6、10、11、12、14 页。
- 未发现明显文字重叠、中文乱码、标题遮挡或关键边界说明缺失。

## 评委审查修复项

- 第 1 页：三枚标签已改为“证据约束 / 多 Agent / 数据闭环”，弱化防御感，边界说明保留在页脚。
- 第 2 页：三张痛点卡已重写，消除项目符号拥挤和不自然断句。
- 第 5 页：13 Agent 已按诊断层、生成层、治理层、评测/后训练层分组。
- 第 6 页：已改为专业视频占位和 3-5 分钟录屏脚本；当前未嵌入 MP4。
- 第 10 页：已增强 Agent Trace 可视化，明确基于 `artifacts/agent_trace` 的 demo/preview 资产。
- 第 11 页：已重做为“沙盘规则评分，不是真实模型实测”，避免 `34/35` 被理解为真实效果。
- 第 12 页：已重做为 `messages / metadata / gate` 三段式结构，删除破损长 JSON。
- 第 14 页：标题已改为“本地代码级收口，服务器待复验”，明确部署边界。

## 内容边界检查

- `已完成真实微调`：`PASS`
- `fine_tuned_model`：`PASS`
- `真实闭环已通过`：`PASS`
- `效果提升 xx%`：`PASS`
- `构造样本是真实用户`：`PASS`

## 必要口径检查

- `Preview 规则评分`：`PASS`
- `不是真实模型实测`：`PASS`
- `ready_for_real_training`：`PASS`
- `for_training=false`：`PASS`
- `真实授权样本不足`：`PASS`
- `作品演示视频待替换`：`PASS`

## 工具说明

- 本次输出为可编辑 PPTX。
- 导出 QA 使用 LibreOffice headless 转 PDF，并用 Poppler `pdftoppm` 导出逐页 PNG。
- 当前未嵌入真实演示视频；后续提供 MP4 后需要替换第 6 页并重新导出 QA。
