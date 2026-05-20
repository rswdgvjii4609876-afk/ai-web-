# 职启智评 competition 当前必看入口

> 当前目录已经做过收口：旧赛道材料、旧 PPT 预览、源材料包、成员原始资料和历史报告已归档到项目外目录。现在看本文件即可知道下一步该读什么。

## 当前状态速记

- 当前最新有效代码基线：阶段 179 工程师 skills 复审收口完成后以 `git log -1 --oneline` 为准；本轮修复基线仍从 `5168028 fix: keep interview feedback nonblocking` 向后推进。
- DeepSeek 当前只保留 `deepseek-v4-pro` 和 `deepseek-v4-flash`，默认 `deepseek-v4-pro`。
- LLM 答题评分、DeepSeek 底层模型归一、单条导出门禁、训练复盘软删除过滤、面试消息安全渲染和后台补授权弹窗属于当前最新修复重点。
- 用户端面试消息不再用 HTML 渲染；后台补授权不再用浏览器 prompt。
- 半自动简历跑批路线已暂停并回滚；历史失败记录不能作为成果或标注对象。
- 当前数据沉淀方式改为人工跑数：服务器用户端人工上传简历，完整跑解析、润色、面试、报告和训练复盘，再到后台“案例标注”人工复核。
- 后台“案例标注”只处理已完成面试；旧完成案例若没有授权入口，可以由管理员补授权并记录审计来源。按当前产品决策，管理员补授权是后台最终确认入口。
- 用户删除已完成面试后，用户端隐藏，后台仍保留供人工复核；未完成面试删除仍清理。
- 当前文件索引以本文为准；旧赛道材料、旧 PPT 预览、源材料包和历史报告均从归档目录找回。

## 现在优先看

1. `opc/README_OPC参赛总入口.md`
   - OPC 参赛主入口。
   - 当前主叙事是：一个人 + AI Agents 的高校就业能力诊断与训练服务单元。

2. `opc/阶段166_职启智评_AI原生结构说明书.md`
   - OPC 报名材料核心说明书。
   - DOCX 版同目录保留：`opc/阶段166_职启智评_AI原生结构说明书.docx`。

3. `opc/阶段166_OPC_AI协同展示页与PPT制作Brief.md`
   - 后续做 OPC PPT 和展示页时优先参考。

4. `opc_ai_coordination/README.md`
   - AI 协同工作流材料入口。
   - 用于说明 ChatGPT、Codex、业务大模型、Eval/后台评分和人工验收如何协同。

5. `职启智评项目升级流程手册.md`
   - 项目阶段推进主控文档。
   - 看当前阶段、下一阶段和不能夸大的边界。

6. `职启智评_OpenAI_SFT真实微调操作手册.md`
   - 真正准备官方 OpenAI SFT 前再看。
   - 当前只作为操作门槛说明，不代表已经完成微调。

## 下一阶段再看

1. `GitHub与服务器发布手册.md`
   - 需要部署、推送、服务器验收时再看。

2. `三岗位真实闭环验收执行包.md`
   - 后续补 C1/C2/C3 真实闭环时再看。

3. `真实案例闭环验收记录.md`
   - 跑完真实案例后回填。

4. `datasets/`
   - C1/C2/C3 验收记录和评测数据模板。

## 当前操作顺序

1. 服务器更新：
   ```bash
   cd /opt/apps/ai-interview
   git pull
   docker compose up -d --build
   docker compose exec -T app alembic upgrade head
   ```
2. 前端硬刷新或无痕登录，确认 DeepSeek 模型下拉只显示 V4 Pro / V4 Flash。
3. 面试页实测连续答题：回答一题后输入框仍可见，评分条可关闭/展开，消息中的 HTML 只作为文本显示。
4. 后台实测“案例标注”：未授权 completed 案例可打开结构化补授权弹窗，填写原因后再保存人工标注。
5. 用户端人工上传简历，按顺序完成：
   ```text
   简历解析 -> 简历润色 -> 新建面试 -> 回答面试 -> 生成报告 -> 训练复盘
   ```
6. 后台进入“案例标注”，只标注人工跑出的有效 completed 案例。
7. 满足已完成、已授权/管理员补授权、人工复核和 PII 门禁后，再考虑 OpenAI SFT 数据准备。

## 现在不要看 / 不要用

- 不要继续使用半自动简历闭环跑批旧路线；相关脚本和临时简历数据已从仓库移除。
- 不要把历史半自动失败记录当成可标注案例。
- 不要标注进行中面试；未完成面试不进入训练/评测样本池。
- 不要把“管理员补授权”说成“用户主动授权”；可以说这是后台管理员最终确认和审计补录。
- 不要继续参考旧 Career-AgentOS PPT 预览作为当前主材料。
- 不要从归档目录恢复旧源材料包到当前阅读入口，除非后续明确要做历史追溯。

## 当前边界

- 可以说：已形成 OPC 参赛主线、AI 协同工作流说明、Career-AgentOS Preview、Agent Trace / Eval Preview / SFT Preview 的工程门禁。
- 可以说：DeepSeek 模型选择已收口为 V4 Pro / V4 Flash，默认 V4 Pro。
- 不能说：C1/C2/C3 真实闭环已经全部通过。
- 不能说：已经完成真实 OpenAI SFT 或已有 `fine_tuned_model`。
- 不能说：半自动简历跑批已经成功。
- 不能把 demo / constructed / simulated 样本说成真实用户数据。
- Eval Preview 是规则沙盘，不是真实 holdout eval，也不是微调后效果证明。

## 已归档材料

项目外归档目录：

`D:\apps\ai-interview_archive\2026-05-19_competition_docs_cleanup`

归档清单：

`D:\apps\ai-interview_archive\2026-05-19_competition_docs_cleanup\ARCHIVE_MANIFEST.md`

已归档内容包括：

- 旧 AI 创新赛 / Career-AgentOS 答辩材料。
- 旧 PPT 预览、PDF、截图和历史生成物。
- `职启智评_比赛版Agent改造包_2026-05-17` 源材料包。
- `职启智评_OPC超级个体备赛包_2026-05-17` 源材料包。
- `chatgpt_sft_analysis_pack` 辅助分析包。
- `成员资料` 原始协作材料。
- `申报书` 旧申报材料和比赛附件。

归档不是删除；需要时从归档目录找回。
