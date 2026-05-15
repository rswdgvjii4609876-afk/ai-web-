# 职启智评答辩 PPT 预览检查记录

- 检查时间：2026-05-15
- PPT 文件：`docs/competition/申报书/final/职启智评_人工智能创新赛答辩PPT_正式版.pptx`
- 资料汇总：`docs/competition/申报书/final/职启智评_答辩PPT资料汇总.md`

## 预览检查命令

```powershell
soffice --headless --convert-to pdf --outdir docs\competition\申报书\final\ppt_preview docs\competition\申报书\final\职启智评_人工智能创新赛答辩PPT_正式版.pptx
pdftoppm -png -r 150 docs\competition\申报书\final\ppt_preview\职启智评_人工智能创新赛答辩PPT_正式版.pdf docs\competition\申报书\final\ppt_preview\slide
```

## 检查结果

- PPTX 可读取，页数为 15 页。
- 已通过 LibreOffice headless 转 PDF，并从 PDF 导出 15 张 PNG 预览。
- 所有预览图尺寸为 2000 x 1125。
- 已检查 `contact_sheet.png` 和关键页：第 5 页视频占位、第 11 页完成度验证、第 12 页创新价值页。
- 第 5 页已保留 16:9 作品演示视频区域；当前本地未发现 `.mp4/.mov/.webm/.avi/.mkv/.wmv` 视频文件。
- 首轮检查发现第 12 页标题换行压到副标题，已收短标题并重新导出。

## 边界说明

- 未使用桌面版 PowerPoint/Keynote 做人工打开校验。
- PPTX 中的文字、形状和截图均为可编辑/可替换元素；截图为嵌入式图片。
