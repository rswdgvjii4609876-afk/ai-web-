# PROJECT_MEMORY.md

## 2026-05-17 最新主线：阶段 166.3 个人模式隐私授权 UI 极简化与默认开启

当前最高优先级按用户最新指令执行：注册页、新建面试/上传简历、开始面试、简历润色、训练复盘、个人设置统一进入个人模式隐私授权默认开启。基础隐私协议与可选数据贡献授权均默认开启并随请求提交；页面只保留截图式极简隐私说明块。

本阶段只改用户端前端 UI 和提交默认值，不改后端数据库、后台导出门禁、隐私协议正文、训练样本准入规则。

## 2026-05-18 阶段 166.2 补交付：AI 原生结构说明书 DOCX 双路径生成

- 已以 `docs/competition/opc/阶段166_职启智评_AI原生结构说明书.md` 为唯一内容源，生成仓库留档 DOCX：`docs/competition/opc/阶段166_职启智评_AI原生结构说明书.docx`。
- 已同步覆盖 E 盘报名材料目录 DOCX，并在覆盖前备份旧版：`E:\dachuang\opc\职启智评_OPC报名材料\AI原生结构说明书\职启智评_AI原生结构说明书.backup_20260518_002326.docx`。
- 已同步 E 盘同名 Markdown，并导出 PDF/PNG 预览到 `docx_preview_20260518_002326/`。
- 已用 `python-docx` 验证 D/E 两份 DOCX 均可读取，标题为“职启智评 AI 原生结构说明书”；已检查预览 contact sheet，中文和表格可读。

## 2026-05-17 最新主线：阶段 166.2 OPC AI 原生结构说明书重生成

阶段 166.1 已锁定“OPC AI 协同展示页 + 12 页 PPT Brief”双轨路线。当前进入阶段 166.2：先重生成报名材料中的《职启智评 AI 原生结构说明书》，把旧版“AI 面试 / 求职诊断系统”口径升级为 OPC 主体口径。

本阶段目标文件：

- 仓库留档：`docs/competition/opc/阶段166_职启智评_AI原生结构说明书.md`
- 报名材料目录：`E:\dachuang\opc\职启智评_OPC报名材料\AI原生结构说明书\职启智评_AI原生结构说明书.md`
- 目标 DOCX：`E:\dachuang\opc\职启智评_OPC报名材料\AI原生结构说明书\职启智评_AI原生结构说明书.docx`

执行要求：

- 先生成 MD，再基于 MD 生成 DOCX。
- 覆盖 DOCX 前必须备份旧版。
- 目标目录现有 JPG 含个人联系方式，默认不插入新版说明书正文。
- 负责人姓名、联系方式、学校/院系等未知信息保留 `【待补】`。
- 仍不得宣称：真实 OpenAI SFT 已完成、已有官方微调模型 ID、C1/C2/C3 真实闭环已全部通过、构造样本是真实用户数据、Eval Preview 是真实模型实测。

## 2026-05-17 最新主线：阶段 166.1 OPC 方案对比、优选与审查 Brief

阶段 165 已完成 OPC 参赛叙事与 AI 协同工作流备赛包。当前进入阶段 166.1：先不直接生成 PPTX 或前端页面，而是把阶段 166 的执行路线锁定为可落地、可审查、可交给后续 agent 执行的决策型材料。

阶段 166.1 结论：

```text
选择 B 方案：OPC AI 协同展示页 + 12 页 PPT Brief 双轨方案。
```

本阶段新增：

- `docs/competition/opc/阶段166_OPC方案对比与推荐结论.md`：比较只做 PPT、展示页 + PPT Brief、只做审查包三种方案，明确选择 B。
- `docs/competition/opc/阶段166_OPC_AI协同展示页与PPT制作Brief.md`：给出 12 页 OPC PPT 结构、`/competition/opc-ai-workflow` 页面草案、AI 协同流程图、人机边界表和证据素材清单。
- `docs/competition/opc/阶段166_OPC边界与验收审查报告.md`：按 OPC 评委、PPT 叙事、AI 协同产品经理、合规边界四个视角做验收审查。

阶段 166 后续拆分：

- 阶段 166.2：基于 Brief 生成 OPC 版答辩 PPT。
- 阶段 166.3：设计或实现 `/competition/opc-ai-workflow` 展示页。

当前边界不变：不启动官方后训练任务，不补跑 C1/C2/C3，不把 demo/preview 或证据格式样例写成真实用户数据。

## 2026-05-17 最新主线：阶段 165 OPC 超级个体参赛叙事与 AI 工作流备赛包

当前最高优先级从 Career-AgentOS 比赛版展示进一步扩展到 OPC 超级个体参赛主线。依据 `docs/competition/职启智评_OPC超级个体备赛包_2026-05-17/` 和联网核验的 OPC 赛事通知，本轮将职启智评重构为：

```text
职启智评 OPC：一个人 + AI Agents 的高校就业能力诊断与训练服务单元
```

本轮已生成：

- `docs/competition/opc/`：OPC 参赛总入口、赛事适配判断、OPC 主叙事、AI 工作流总图、人机协同分工图、PPT 结构、3 分钟/8 分钟讲稿、评委问答、日常运行手册、三个月补实路线和成果边界。
- `docs/competition/opc/live_test_drills/`：30/45/60 分钟复赛限时实测训练题、评分表和标准作答模板。
- `docs/competition/opc_ai_coordination/`：ChatGPT、Codex、业务大模型、Eval/后台评分之间的 AI 使用顺序、Prompt 模板、交接协议和答辩话术。
- `artifacts/opc_ai_coordination/`：AI 协同 trace、prompt chain、Codex task bundle、handoff log 样例。
- `docs/agents/`：新增 OPC 角色体系索引和 Competition Research、Codex Engineering、Architecture Review、SFT Dataset、Defense Coach 等角色文档。

当前 OPC 答辩口径：

- 可以说：我作为 OPC Commander，把 ChatGPT、Codex、业务大模型、Eval/后台评分组织成高校就业服务 AI 原生工作流。
- 可以说：项目已有可运行原型、Career-AgentOS Preview、Agent Trace、Eval Preview、SFT-ready 门禁和后台人工评分链路。
- 不得说：三岗位真实闭环已全部通过、真实 OpenAI 后训练已经落地、已有官方微调模型 ID、demo_constructed 是真实用户数据、Eval Preview 是真实模型实测。

阶段 166 建议：生成 OPC 版答辩 PPT 或新增 `/competition/opc-ai-workflow` 展示页；真实 C1/C2/C3 和真实 OpenAI SFT 继续进入三个月补实路线，不删除、不作废。

## 2026-05-17 最新主线：阶段 159-164 六子 Agent 复审后的功能完善
当前最高优先级从“阶段 152-158 全链条代码级收口”推进到“阶段 159-164 复审修复闭环”。依据六个子 agent 对 `main@924fbf7` 的二次只读审查，本轮结论是：先修唯一 must-fix，再补隐私、导出、后台权限、用户流、SFT 审计、Competition Preview 和部署验收的 should-fix。

已执行口径：
- 阶段 159：`high_risk_claims` 只保留候选人简历、回答或候选人证据来源；岗位画像、知识库切片和 RAG 召回只进入岗位校准/追问依据，不能写成候选人真实经历。
- 阶段 160：数据贡献默认授权必须匹配当前版本；Profile 返回 `data_contribution_consent_valid`；头像上传拒绝 SVG 和伪造 MIME；训练/评测导出产物增加最终 PII 扫描。
- 阶段 161：后台无权限/未授权/未完成案例的评分表单整体禁用；初始管理员脚本避免非 root 创建混乱 superadmin；学习计划 AI/web-search 增强不再覆盖路线元数据；流式答题失败时回滚或刷新乐观消息。
- 阶段 162：OpenAI SFT 样本必须包含 reviewer presence/hash；JSONL 非 object 行直接失败；eval 默认使用 `job_record.json` 中的 base model；`--force-new-job` 不静默覆盖旧 job 记录。
- 阶段 163：Competition Preview SFT API 返回全部已校验 preview records；前端 Eval 面板展示 baseline/agent 两行七维明细；Swagger 和答辩模板加 future-only 标记。
- 阶段 164：`stage138_server_closed_loop_verify.sh --deploy` 改为重建完整根目录 Docker Compose 栈；Celery beat healthcheck 增加 broker 连接探测；旧后端 deploy 脚本标记为 legacy。

仍不得宣称：C1/C2/C3 真实闭环已通过、真实 OpenAI SFT 已完成、已有 `fine_tuned_model`、构造样本是真实用户数据、微调效果有固定百分比提升。

## 2026-05-17 最新主线：阶段 152-158 全链条代码审查修复

当前最高优先级已从单点 Career-AgentOS Preview 修复，升级为全链条代码级收口。依据 6 个子 agent 的审查结果，本轮按“数据安全优先、用户闭环第二、比赛展示第三、SFT 真实训练门禁第四、部署收口最后”执行阶段 152-158。

已落地的阶段口径：

- 阶段 152：P0 数据安全与隐私授权硬门禁。基础隐私协议必须匹配当前版本；未同意基础协议的老用户不能继续上传、润色、学习计划、面试、报告或训练复盘；生产环境不公开 `uploads/resumes`，只公开头像；生产环境不挂载 client/backoffice Swagger/OpenAPI。
- 阶段 153：后台权限、人工评分与导出准入。新增 `can_review_cases`、`can_export_datasets`、`can_delete_records`；训练/评测导出统一要求本次案例授权、面试完成、人工复核 `review_status=reviewed`，并执行 PII 脱敏/拦截。
- 阶段 154：用户主链路稳定性。流式答题使用统一 API baseURL/token 处理；答题提交增加 `question_index` 与状态保护；RAG/岗位知识库只能作为岗位要求和追问参考，不能写成候选人真实经历；报告坏 JSON 不再静默伪装为空报告。
- 阶段 155：简历润色、快照与学习任务质量。简历润色增加“可改但不造假”确定性校验；学习计划优先使用 `resume_evaluation_snapshot`；学习任务质量由后端计算并返回。
- 阶段 156：Career-AgentOS Preview 严谨化。Eval Preview 固定 7 维 35 分；每个 case 必须包含 `baseline_prompt_preview=19/35` 与 `agent_optimized=34/35`；Trace 必须包含完整 Agent 顺序；旧 `/api/v1/demo/competition` 与旧 `CompetitionDemo.vue` 已清理。
- 阶段 157：OpenAI SFT 真实训练门禁。`--real-jsonl` 已禁用，避免自声明 JSONL 伪造授权/复核元数据；create/check/eval 全部进入 shared preflight，未授权、未复核、含 PII、样本不足、job 不匹配或非官方 OpenAI base URL 均不得创建或绑定真实 job。
- 阶段 158：部署与健康检查。health 增加 Alembic head 检查；生产配置增加 fail-fast；Celery 并发进入数据库容量预算；部署文档统一根目录 `docker compose` 口径。

当前仍不能宣称：C1/C2/C3 真实闭环已通过、真实 OpenAI SFT 已完成、已有 `fine_tuned_model`、构造样本是真实用户数据、微调效果有固定百分比提升。

更新时间：2026-05-17

项目目录：`D:\apps\ai-interview`
服务器目录：`/opt/apps/ai-interview`
GitHub 仓库：`YiyuZh/ai-interview`
主控文档：`docs/competition/职启智评项目升级流程手册.md`
详细历史：`任务记录文档.md`

## 1. 当前正在实现的功能目标

当前项目主线不是单纯“AI 面试官”，而是“就业能力诊断与提升平台”：

`简历解析 -> 目标岗位 -> 岗位画像/岗位知识库 -> 简历证据评分 -> 能力差距诊断 -> 简历润色 -> 学习任务 -> AI 模拟面试 -> 报告 -> 训练复盘 -> 人工评分沉淀`

最近正在收口的重点：

1. 后台管理员账号和权限管理。
2. 简历 PDF 解析兼容性和开始面试稳定性。
3. PostgreSQL 并发治理和数据库容量自检。
4. 核心链路自动自检，为后续三岗位真实闭环验收做准备。
5. 阶段 150.1 深度代码审查修复：当前最高优先级是完成 Career-AgentOS 比赛展示链路的代码级审查、子 agent 二次复查、测试、提交和推送，再进入服务器部署验收。

当前策略：

- 保留 PostgreSQL，不迁移 MySQL。
- 成员资料不再作为新岗位画像，而是归并到已有标准岗位画像。
- 简历评分、润色、学习计划、AI 面试、报告和复盘要统一使用简历评价快照和证据状态。
- 真实案例进入后台人工评分、评测样本和比赛材料前，必须完成本次案例去标识化数据贡献授权；不同意不影响核心功能使用，但不能计入阶段 138 有效沉淀样本。
- 阶段 139/139.1 已完成本地功能收口；用户已明确要求继续把 C1/C2/C3 验收后移，当前先做有利于答辩展示的微调准备层。
- 阶段 141 已新增大模型微调与答辩展示方案文档；阶段 142 已落地“可授权、可人工复核、可导出”的微调准备样本；阶段 143 已生成答辩可用的微调准备 Markdown 报告；阶段 144 启动 OpenAI SFT 脚本闭环。只有 OpenAI job 成功并取得 `fine_tuned_model` 后，才允许写“已完成一次 OpenAI SFT 微调实验”。
- 阶段 145 起临时切换到比赛版 `Career-AgentOS` 改造主线：先做可展示、可答辩、可追溯的多 Agent 架构、演示沙盘、Agent Trace、Eval Preview 和 SFT Preview；真实 OpenAI SFT、C1/C2/C3 闭环和服务器真实样本继续后移但不作废。
- `docs/competition/职启智评_比赛版Agent改造包_2026-05-17/` 是当前比赛版改造的源材料包，后续阶段以其中 README、Codex 总提示词、适应性改造任务清单和各规范文档为依据。
- 答辩口径必须分层：可以说“已完成 SFT-ready 数据闭环设计、Agent Trace 方案、微调任务设计”，不能说“已完成真实微调”“已有 fine_tuned_model”“构造样本是真实用户数据”。
- 阶段 145.1 已确认比赛版 Agent 包遗漏“简历润色”功能，后续 Career-AgentOS 固定包含 `简历润色 Agent / Resume Polish Agent`：位置在能力差距诊断之后、面试追问之前；职责是基于证据状态和岗位画像输出“可改但不造假”的岗位化表达建议。
- 阶段 146-149 深度落地新增可执行资产链：`docs/agents/`、`demo_cases/`、`artifacts/agent_trace/`、`artifacts/eval/`、`artifacts/sft_preview/`、后端 `agent_orchestrator`、脚本入口和用户端 `/competition/agent-trace`；这些资产是比赛 Preview，不等同真实用户样本或真实 OpenAI 微调。

## 2. 用户提出过的关键需求细节

### 2.1 管理后台账号与权限

- 原始后台账号固定为 `autsky6666@gmail.com`。
- 只有该原始账号默认拥有“管理员管理权限”。
- 新增管理员时可以设置对方是否拥有管理员管理权限。
- 普通管理员不能新增、删除、授权管理员。
- 原始账号不能被删除、禁用、收回权限。
- 所有管理员都应能修改自己的后台密码。
- 不在仓库保存真实密码；服务器创建首个管理员时通过环境变量输入。

### 2.2 简历解析和开始面试稳定性

- 用户上传 `2590603008詹已誉简历.pdf` 后，页面曾显示解析成功，但点击开始面试闪退。
- 该 PDF 是文字型 PDF，`pdfplumber` 能抽出文本，核心问题更可能是结构化字段不稳定，而不是必须 OCR。
- 解析要兼容多样 PDF，先优先 `pdfplumber`，再 `PyPDF2`，只有低质量或空文本才走 OCR fallback。
- OCR 不能默认全量开启，必须由 `ENABLE_RESUME_OCR=true` 控制。
- 页面要显示解析质量、抽取方式、是否 OCR、缺失字段。
- 开始面试失败时返回可读错误，不让前端闪退。

### 2.3 学习任务、学习路线和评价口径

- 学习任务应服务器持久化，不能只存在 localStorage。
- 后台可以维护基础学习路线模板和成熟学习计划。
- 前台用户可根据缺失能力生成学习计划，也可使用成熟计划并编辑任务。
- 简历评分、能力诊断、简历润色、AI 面试、学习计划、复盘需要统一简历评价数据口径。
- `claimed_only`、`indirect`、`missing` 不能在不同页面显示冲突结论。
- 简历只写“熟悉 Redis / SQL”等声明，不能直接判定掌握，应优先面试验证。

### 2.4 岗位知识库和成员资料

- 系统原来已有 Python 后端等标准岗位画像。
- 成员搜集的岗位资料本质是补充校准，不应作为新的并列岗位画像。
- 问答经验应有更清晰的管理入口。
- 第一版仍可复用岗位画像 `## 问答经验` 分区和切片体系，不必立刻建独立面经表。
- 岗位知识库只能作为岗位要求、追问方向和润色参考，不能当作候选人真实经历。

### 2.5 数据库并发与 MySQL

- 用户担心 PostgreSQL 拼写和多人并发，提出是否切 MySQL。
- 当前结论：不迁移 MySQL，先做 PostgreSQL 连接池和容量治理。
- 原因：项目深度依赖 `asyncpg`、Alembic、PostgreSQL `JSONB`、知识切片和报告快照。
- 并发瓶颈更可能是连接池过大、worker 数、LLM API 调用慢和服务器资源。

### 2.6 Git 和资料提交

- 不要再随意 `git add .`。
- 用户希望后续完成明确的一轮代码或文档改动后，默认由 Codex 精准暂存并本地 commit。
- 默认只 commit 本轮相关文件；push、强制重置、删除未跟踪大文件等动作仍需明确指令。
- 当前应精准提交代码和记忆文件，排除 `.codex_tmp_*`、申报书大文件、查新 PDF、成员原始资料、构建产物。
- 用户确认当前两个 tracked 删除项可以保留删除并提交。

## 3. 已经完成的改动

### 3.1 阶段 133：核心功能自动化收口

新增离线自检脚本：

- `ai-interview-backend/app/scripts/check_core_feature_flow.py`
- `ai-interview-backend/tests/test_check_core_feature_flow.py`

作用：

- 不调用外部大模型。
- 不写业务数据库。
- 使用合成样例检查 Python 后端、产品助理、人力资源专员三类岗位。
- 检查成员知识包、统一评价快照、简历润色、学习计划、AI 面试路由和验证目标。

注意：

- 自检不能替代真实简历和真实问答验收。
- 生成报告目录 `docs/competition/core_feature_flow_reports/` 本轮不提交。

### 3.2 阶段 135：后台管理员账号与权限管理

后端完成：

- `admins` 表新增 `can_manage_admins` 字段。
- 新增迁移：`ai-interview-backend/migrations/versions/a2c4e6f8b135_add_admin_management_permission.py`
- root 账号 `autsky6666@gmail.com` 自动拥有管理员管理权限。
- 只有 root 可授予或收回 `can_manage_admins`。
- root 不可删除、不可禁用、不可收回权限。
- 管理员不可删除自己。
- 删除管理员时硬删除并清理 token。

后台端完成：

- 新增 `ai-interview-admin/src/views/Admins.vue`
- 新增 `ai-interview-admin/src/views/AccountSettings.vue`
- 侧边栏按权限显示管理员管理。
- 登录页默认邮箱改为 `autsky6666@gmail.com`。
- auth store 保存 `can_manage_admins` 和 `is_root_admin`。

测试：

- `ai-interview-backend/tests/test_admin_permissions.py`

### 3.3 阶段 136：简历解析兼容性和开始面试稳定性

后端新增：

- `ai-interview-backend/app/services/client/resume_text_extractor.py`
- `ai-interview-backend/app/services/client/resume_normalizer.py`
- `ai-interview-backend/tests/test_resume_text_extractor.py`
- `ai-interview-backend/tests/test_resume_normalizer.py`

核心逻辑：

- PDF 文本抽取优先 `pdfplumber`，备用 `PyPDF2`。
- 自动选择质量更高的文本。
- OCR fallback 使用 `PyMuPDF + Tesseract`，由 `ENABLE_RESUME_OCR=true` 控制。
- 写入 `analysis.extraction_diagnostics`、`analysis.parse_quality`、`analysis.normalized_resume`。
- 兼容 AI 返回 string/list/dict 混合结构。
- 开始面试读取归一结构；字段不足返回可读错误。

前端完成：

- `ai-interview-frontend/src/views/ResumeUpload.vue`
- 上传/分析页显示解析质量、抽取方式、OCR 状态、缺失字段和告警。
- 开始面试失败时保留页面状态并显示方向性提示。

依赖和 Docker：

- `ai-interview-backend/requirements.txt` 增加 `PyMuPDF`。
- Dockerfile / Dockerfile.dev 增加 Tesseract 中文和英文 OCR 包。
- `.env.example` 增加 `ENABLE_RESUME_OCR=false`。

### 3.4 阶段 137：PostgreSQL 并发治理

完成：

- `app/core/config.py` 新增连接池环境变量：
  - `DB_POOL_SIZE`
  - `DB_MAX_OVERFLOW`
  - `DB_POOL_TIMEOUT`
  - `DB_POOL_RECYCLE`
  - `DB_SCHEDULER_POOL_SIZE`
  - `DB_SCHEDULER_MAX_OVERFLOW`
- `app/db/base.py` 使用配置值，不再硬编码 `pool_size=20`、`max_overflow=10`。
- 新增 `ai-interview-backend/app/scripts/check_database_capacity.py`。
- `.env.example` 和后端 `.env.example` 增加保守连接池默认值。

脚本能力：

- 只读检查 PostgreSQL。
- 输出 max_connections、当前连接数、active 连接、状态分布、核心表行数、最大表、长运行查询和建议。
- 本机缺 `asyncpg` 时能输出可读错误；服务器 Docker 容器内应正常运行。

### 3.5 阶段 138：服务器真实闭环验收与数据沉淀收口

新增服务器闭环验收工具：

- `scripts/stage138_server_closed_loop_verify.sh`
- `scripts/validate_stage138_closed_loop.py`

作用：

- 阶段 138 不新增业务页面、接口或数据库表。
- 先把阶段 135 管理员权限、阶段 136 真实 PDF 简历解析、阶段 137 PostgreSQL 容量自检统一放到服务器验收脚本里。
- 用 CSV 明确检查 R1/R2/R3 三条真实案例是否完成完整闭环。
- 每条真实案例必须覆盖：上传简历、能力诊断、简历润色、学习任务、至少 3 轮面试、报告、训练复盘、本次案例去标识化数据贡献授权、后台人工评分。
- `--readiness-only` 可用于人工跑测前的服务器预检，此时 C1/C2/C3 未完成只记为 WARN。
- 完整模式下，CSV 未达到阶段 138 口径会返回 FAIL。

当前状态：

- 阶段 138 工具和文档口径已落地。
- 2026-05-15 服务器 commit `b42cff1` 已执行 `bash scripts/stage138_server_closed_loop_verify.sh --readiness-only`，结论为 `WARN`。
- 该 WARN 只来自 C1/C2/C3 尚未跑测；服务器 readiness 关键项已通过：Alembic、健康检查、PostgreSQL 容量、阶段 133 核心自检、root 管理员权限、关键日志扫描。
- 隐私授权升级后，阶段 138 CSV 和检查器新增 `data_contribution_consent_status`，用于确认本次案例是否允许进入去标识化评测库、比赛材料、质量改进和人工评分沉淀。
- 真实 C1/C2/C3 案例仍待服务器人工跑测和 CSV 回填。
- 未完成前不要新增页面、接口、表结构、MySQL 迁移或模型策略来绕过真实验收。

### 3.6 阶段 138 服务器构建源加速修复

服务器执行 `docker compose up -d --build` 时曾卡在后端生产镜像的 `apt-get update && apt-get install`，日志显示仍访问 `deb.debian.org`。

已处理：

- 后端生产 `ai-interview-backend/Dockerfile` 保持 pip 使用清华 PyPI。
- 新增 `APT_DEBIAN_MIRROR` 和 `APT_SECURITY_MIRROR` 构建参数。
- 在 `apt-get update` 前把 Debian 源替换为清华镜像。
- 根目录 `docker-compose.yml` 和后端 `docker-compose.prod.yml` 显式传入清华 Debian 镜像参数。

服务器重新部署建议：

```bash
cd /opt/apps/ai-interview
git pull --ff-only
docker compose build --progress=plain app
docker compose up -d --build app admin frontend
```

### 3.7 阶段 139：授权转化、后台准入与学习任务质检

本阶段由用户确认把 C1/C2/C3 后置后启动，目标是先补小功能，提升后续真实数据沉淀质量。

处理范围：

- 用户端报告页和训练复盘页复用的本次案例授权卡增强文案，突出授权后可针对性升级岗位画像、追问策略、评分规则、报告建议和学习任务质量。
- 后台案例标注工作台增加授权统计、筛选、表格列和未授权保存禁用，后端仍保持未授权不能人工评分沉淀的兜底。
- 评测样本页把样本口径改为“已授权完成测评”，固定规则包含 `data_contribution_consent=true`。
- 学习任务页增加高质量/可用/待完善质检状态、质量筛选和缺失项提示。

阶段 139.1 收口：

- 后台面试详情页同步数据授权准入口径。
- 未授权面试详情页不能保存人工标注，也不能导出评测样本。
- 该补丁只补前端准入提示与按钮状态，不新增数据库表、接口或模型策略。

### 3.8 阶段 140：阶段 139 服务器部署与三岗位真实闭环重启

阶段 140 不是新功能阶段。目标是先把阶段 139/139.1 部署到服务器，烟测授权准入和学习任务质检，再回到 C1/C2/C3。

服务器部署后必须检查：

- 报告页/训练复盘页本次案例数据贡献授权卡可见、可更新。
- 后台案例工作台和后台面试详情页都不能对未授权案例保存人工标注。
- 评测样本页固定规则包含 `data_contribution_consent=true`。
- 学习任务页能按高质量/可用/待完善筛选并显示缺失项。
- readiness 仍通过；如果只剩 C1/C2/C3 未回填，应保持 WARN 而不是 PASS。

### 3.9 阶段 141/142：大模型微调准备与答辩展示增强

用户要求继续把 C1/C2/C3 验收后移，先做对比赛答辩更有展示价值的“大模型微调准备”能力。

阶段 141 已完成：

- 新增 `docs/competition/职启智评_大模型微调与答辩展示升级方案.md`。
- 明确答辩可说“微调数据准备链路”，不可说“已完成大模型微调”。

阶段 142 本轮目标：

- 后台评测样本页增加“大模型微调准备层”统计和 JSONL 导出入口。
- 后端基于已授权、已人工复核、带质量信号的样本生成 `instruction/input/output/metadata` JSONL。
- 幻觉样本单独进入反例 JSONL，正向 SFT 样本要求不带幻觉标记。
- C1/C2/C3 不删除、不作废，后续仍需按真实闭环执行包跑测和回填。

阶段 143 本轮目标：

- 后端基于同一批已授权、已人工复核样本生成微调准备 Markdown 报告。
- 报告覆盖当前结论、数据来源与准入规则、去标识化与保留字段、样本分层、岗位覆盖、可训练任务、风险控制和下一步。
- 后台评测样本页增加“导出准备报告 MD”按钮，方便直接放入答辩资料包。
- 报告必须写明“微调准备数据链路”，不能写成“已完成真实 SFT/LoRA 训练”。

### 3.10 阶段 144：OpenAI SFT 真实微调启动

用户已选择 `OpenAI SFT` 和“真样本 + 构造样本”路线。本阶段不做 UI，不新增数据库表，先补脚本级训练闭环：

- 将现有 `instruction/input/output/metadata` JSONL 转为 OpenAI chat fine-tuning JSONL。
- 上传训练文件前保留本地 manifest，训练文件只包含 `messages`，metadata 不进入 assistant 输出。
- 构造样本只用于追问生成任务补齐格式和三岗位覆盖，必须标记 `sample_origin=constructed`，不得说成真实用户数据。
- 创建真实 OpenAI fine-tuning job 前必须满足：真实授权样本不少于 3 条，训练集不少于 10 条，`OPENAI_API_KEY` 与 `OPENAI_FINE_TUNE_BASE_MODEL` 已配置。
- 新增脚本：`prepare_openai_fine_tuning_dataset`、`create_openai_fine_tuning_job`、`check_openai_fine_tuning_job`、`run_fine_tuning_eval`。
- 训练记录只写 job id、base model、fine-tuned model id、样本统计和 eval 结果，不写 API Key，不提交真实简历原文。

### 3.11 阶段 145：Career-AgentOS 比赛版改造主线接管

用户新增 `docs/competition/职启智评_比赛版Agent改造包_2026-05-17/`，要求以比赛获奖和答辩展示为最高优先级，把项目从“AI 面试官/微调准备”进一步升级为 `Career-AgentOS` 多 Agent 就业能力诊断与训练平台。

阶段 145 的定位：

- 只做主线切换、记忆文档和升级流程收口，不直接新增业务代码、数据库表、前端页面或训练任务。
- 将阶段 144 真实 OpenAI SFT、阶段 138/140 C1/C2/C3 真实闭环后移，但不删除、不作废。
- 将未执行阶段写入升级流程手册并置顶：阶段 146 P0 答辩资产与 Agent 角色文档，阶段 147 三岗位演示沙盘与 Trace/Eval/SFT Preview，阶段 148 后端 Agent Orchestrator，阶段 149 前端/后台展示页，阶段 150 赛前部署验收，阶段 151 三个月补实路线。
- 允许强势表达“多智能体就业诊断架构设计”“SFT-ready 数据闭环设计”“三岗位演示沙盘与 Agent Trace 方案”，但禁止伪造真实 fine-tuning job、模型 ID、真实样本规模或固定提升百分比。

### 3.12 阶段 145.1：简历润色 Agent 缺口收口

阶段 145.1 是对比赛版 Agent 改造包的补漏：旧项目已经有阶段 122/131 的简历润色功能，但阶段 145 首次纳入 Career-AgentOS 时没有把润色写成独立 Agent。

收口口径：

- 新增 `Resume Polish Agent / 简历润色 Agent` 到比赛版架构、角色卡、Trace、Eval、SFT Preview 和答辩问答。
- 固定链路为：简历证据 -> 岗位画像 -> 能力差距 -> 简历润色 -> 面试追问 -> 报告 -> 学习任务 -> 数据治理 -> Eval -> SFT Preview。
- 简历润色 Agent 只能强化已有真实证据、提示待补证据和风险，不能编造项目、公司、时间、指标或技术经历。

### 3.13 阶段 146-149：Career-AgentOS 比赛版深度落地

阶段 146-149 将比赛版改造从文档叙事推进到可运行演示闭环：

- `docs/agents/` 新增 13 个 Agent 角色文档，覆盖 OPC、比赛叙事、简历证据、岗位画像、能力差距、简历润色、面试追问、报告、学习任务、数据治理、Eval、后训练路线和评委拷问。
- 新增三岗位 `demo_cases`，全部标记 `sample_origin=demo_constructed`、`for_training=false`、`for_competition_demo=true`。
- 新增 `Agent Trace -> Eval Preview -> SFT Preview` 脚本链和后端只读展示接口 `/api/v1/competition/...`。
- 用户端新增 `/competition/agent-trace`，旧 `/competition-demo` 改为跳转新展示页；后台评测样本页增加比赛 Preview 说明。
- 当前仍不能说真实 OpenAI SFT 已完成；所有 demo/preview 资产只用于比赛展示和链路验证。

### 3.14 阶段 150.1：Career-AgentOS 深度代码审查与修复闭环

阶段 150.1 针对用户指出的“审查不够深入”进行代码级收口，范围覆盖后端数据流、Competition API、安全边界、脚本复现、前端消费、后台 Preview 错误处理和测试覆盖。

- 子 agent 只读深审发现的 must-fix 已纳入修复范围：脚本任意 cwd/直接文件执行、Eval Preview summary 二次校验、Competition API case_id allowlist、SFT Preview bundle 校验。
- 后端统一使用 `asset_guardrails` 校验 demo/trace/eval/SFT preview 资产，要求 `sample_origin=demo_constructed`、`for_training=false`、`for_competition_demo=true`，并扫描邮箱、手机号、身份证号、学号等直接身份标识。
- Competition API 在读取 trace 和 eval 前先校验 `case_id`，只允许 C1/C2/C3 固定案例；不合规磁盘资产不返回给前端。
- 脚本链默认输出到仓库根目录 `demo_cases/` 和 `artifacts/`，并补根层 `app` shim，使 `python -m app.scripts.generate_competition_assets` 可从仓库根目录运行；直接执行脚本文件时也能自动定位后端包。
- 用户端 `/competition/agent-trace` 会消费 `eval-preview/{case_id}`，展示 `baseline_prompt_preview` 与 `agent_optimized` 的 Preview 对照，并在前端二次保证 C1/C2/C3 顺序。
- 后台 `EvaluationDatasets.vue` 对 competition Preview 加载失败给出可见错误，不再只吞掉异常。
- 本阶段结论只能写“比赛 Preview 链路代码级审查通过/可进入服务器部署验收”，不能写真实 C1/C2/C3 已通过、真实 OpenAI SFT 已完成或已有 `fine_tuned_model`。

## 4. 涉及的文件和核心逻辑

### 4.1 后端核心

- `ai-interview-backend/app/core/config.py`
  - 管理环境变量。
  - 包含 OCR 开关、管理员邮箱、数据库连接池参数。

- `ai-interview-backend/app/db/base.py`
  - 创建 SQLAlchemy async engine。
  - 当前使用 `postgresql+asyncpg`。
  - 主应用和 scheduler 使用独立连接池配置。

- `ai-interview-backend/app/api/backoffice/v1/admin.py`
  - 后台管理员列表、新增、编辑、删除、改密接口。
  - 管理员管理权限以 `can_manage_admins` 为准。

- `ai-interview-backend/app/services/backoffice/admin.py`
  - 后台 token、管理员认证和权限辅助逻辑。

- `ai-interview-backend/app/models/admin.py`
  - Admin 模型，新增 `can_manage_admins`。

- `ai-interview-backend/app/services/client/resume_service.py`
  - 简历上传、文本抽取、AI 解析、分析 JSON 构建。
  - 现在会写入解析质量和归一结构。

- `ai-interview-backend/app/services/client/interview_service.py`
  - 开始面试、问题路由、报告和样本构建。
  - 现在开始面试时会兜底归一旧简历结构。

- `ai-interview-backend/app/services/client/resume_text_extractor.py`
  - PDF 抽取和 OCR fallback。

- `ai-interview-backend/app/services/client/resume_normalizer.py`
  - 简历结构归一。

- `ai-interview-backend/app/scripts/check_core_feature_flow.py`
  - 离线核心功能自检。

- `ai-interview-backend/app/scripts/check_database_capacity.py`
  - PostgreSQL 容量自检。

### 4.2 前端和后台

- `ai-interview-admin/src/views/Admins.vue`
  - 管理员管理页面。

- `ai-interview-admin/src/views/Cases.vue`
  - 阶段 139 后台授权准入与人工标注入口。

- `ai-interview-admin/src/views/InterviewDetail.vue`
  - 阶段 139.1 后台面试详情页授权准入补齐。

- `ai-interview-admin/src/views/EvaluationDatasets.vue`
  - 阶段 139 评测样本授权口径展示。

- `ai-interview-admin/src/views/AccountSettings.vue`
  - 后台账号设置和修改密码。

- `ai-interview-admin/src/stores/auth.js`
  - 保存当前管理员权限状态。

- `ai-interview-admin/src/router/index.js`
  - 管理员管理和账号设置路由。

- `ai-interview-admin/src/App.vue`
  - 侧边栏入口显示控制。

- `ai-interview-frontend/src/views/ResumeUpload.vue`
  - 简历解析质量展示和开始面试错误提示。

- `ai-interview-frontend/src/components/CaseDataContributionCard.vue`
  - 报告页和训练复盘页复用的本次案例数据贡献授权卡。

- `ai-interview-frontend/src/views/LearningTasks.vue`
  - 阶段 139 学习任务质量提示和筛选。

### 4.3 文档和流程

- `docs/competition/职启智评项目升级流程手册.md`
  - 当前主控路线。
  - 已追加阶段 135、136、137、138、139、140。

- `docs/competition/三岗位真实闭环验收执行包.md`
  - 阶段 138 C1/C2/C3 执行入口。

- `docs/competition/真实案例闭环验收记录.md`
  - 阶段 138 记录和机器检查口径。

- `scripts/stage138_server_closed_loop_verify.sh`
  - 服务器 readiness 和闭环验收报告脚本。

- `scripts/validate_stage138_closed_loop.py`
  - C1/C2/C3 真实闭环 CSV 检查脚本。

- `scripts/validate_real_closed_loop_records.py`
  - 通用真实闭环 CSV 检查脚本；当前也把 `data_contribution_consent_status` 纳入完整流程统计。
- `docs/competition/职启智评_比赛版Agent改造包_2026-05-17/`
  - 阶段 145 起的比赛版 Career-AgentOS 改造源材料包。
  - 当前优先读取 `README_先读_比赛版Agent改造总入口.md`、`00_Codex总提示词_直接复制.md`、`10_Codex适应性改造任务清单.md`。

- `任务记录文档.md`
  - 长历史记录。
  - 已追加阶段 135、136、137、138、139。

## 5. 当前未完成事项

1. 阶段 138 三岗位真实闭环和数据沉淀：
   - 服务器 readiness 已通过；C1/C2/C3 真实案例按用户要求曾后置到阶段 139 之后。
   - 阶段 139/139.1 本地功能收口完成后，进入阶段 140：先部署并烟测，再按执行包跑 C1/C2/C3。
   - 每个案例补齐诊断、润色、学习任务、至少 3 轮面试、报告、训练复盘、本次案例去标识化数据贡献授权和后台人工评分。
   - 回填 `docs/competition/真实案例闭环验收记录.md` 和 CSV。
   - 最后执行 `python scripts/validate_stage138_closed_loop.py`，必须 `result=PASS`。

2. 阶段 135 服务器验收：
   - `alembic upgrade head` 已在服务器执行到 `a2c4e6f8b135`。
   - root 管理员 `autsky6666@gmail.com|true` 已通过 SQL 检查。
   - 仍需人工测试新增管理员、授权、删除、改密。

3. 阶段 136 服务器真实 PDF 验收：
   - 上传真实 PDF。
   - 检查 `parse_quality` 和 `normalized_resume`。
   - 点击开始模拟面试，确认不闪退。
   - 若扫描版 PDF 要支持，再开启 `ENABLE_RESUME_OCR=true`。

4. 阶段 137 服务器数据库容量自检：
   - 服务器已执行 `python -m app.scripts.check_database_capacity`。
   - 当前 PostgreSQL `max_connections=100`，当前连接数 `2`，理论应用连接容量 `45`，未发现明显容量风险。
   - 继续保持小连接池并观察真实跑测日志。

5. 阶段 132 三岗位真实闭环：
   - C1：Python 后端开发工程师。
   - C2：产品助理/产品经理实习生。
   - C3：人力资源专员。
   - 每个案例至少 3 轮问答，推荐 5 轮。

6. 阶段 134 服务器归并验证：
   - 成员补充资料应归并到标准岗位画像。
   - 旧 `成员资料补充：{岗位}` 应停用但可追溯。
   - 面试经验管理入口需要后台真实使用验收。

7. 学习任务和学习计划真实页面验收：
   - 学习任务保存后刷新仍保留。
   - AI 生成计划和成熟计划模式需要服务器确认。
   - 阶段 139 新增任务质量提示后，需要确认高质量/可用/待完善筛选和缺失项提示。

8. 申报书、查新报告、成员资料原始文件：
   - 当前大量未跟踪文件未提交。
   - 本次提交计划故意排除这些大文件。

## 6. 已知问题、失败尝试和不能走的方案

### 6.1 不能直接 `git add .`

当前工作区混有：

- `.codex_tmp_*` 临时目录。
- 申报书 final 大文件。
- 查新 PDF、截图、压缩包。
- 成员资料原始待检查文件。
- 多个阶段代码改动。

直接 `git add .` 会污染仓库。

### 6.2 当前不迁移 MySQL

原因：

- 项目深度依赖 PostgreSQL JSONB。
- Alembic 迁移里直接使用 `postgresql.JSONB`。
- 切换 MySQL 要重写驱动、迁移、JSON 字段、测试和数据搬迁。
- 当前并发风险优先从连接池、worker、LLM 调用和服务器资源处理。

### 6.3 不能把成员资料作为新岗位画像长期使用

阶段 126/128 的 `成员资料补充：{岗位}` 是临时低风险策略。正式策略：

- 标准岗位画像是主来源。
- 成员资料归并为补充层。
- 面试经验作为岗位画像内的一等内容管理。

### 6.4 不能默认所有 PDF 走 OCR

原因：

- OCR 慢。
- 普通文字版 PDF 可直接抽取。
- OCR 只用于空文本、低质量、扫描版 PDF。
- OCR 由 `ENABLE_RESUME_OCR=true` 显式开启。

### 6.5 不能把岗位知识库当候选人经历

岗位知识库只能用于：

- 岗位要求。
- 面试追问方向。
- 简历润色建议的岗位表达参考。
- 学习任务和能力模型参考。

不能用于：

- 断言候选人真实做过某项目。
- 编造公司、时间、指标、技术栈。

### 6.6 本机容量脚本可能缺 asyncpg

在本机直接执行：

```powershell
python -m app.scripts.check_database_capacity
```

可能出现 `asyncpg` 缺失。脚本现在会输出可读错误。服务器 Docker app 容器内应有依赖。

## 7. 下一步建议

### 7.0 阶段 140 优先执行

阶段 139/139.1 本地收口后，当前优先做服务器部署和烟测：

```bash
cd /opt/apps/ai-interview
git pull --ff-only
docker compose up -d --build app admin frontend
docker compose exec -T app alembic upgrade head
bash scripts/stage138_server_closed_loop_verify.sh --readiness-only
```

烟测重点：

- 报告页和训练复盘页授权卡可见、可更新。
- 后台案例工作台授权统计、筛选、未授权禁用可用。
- 后台面试详情页未授权时不能保存标注或导出评测样本。
- 评测样本页显示“已授权完成测评”和 `data_contribution_consent=true`。
- 学习任务页任务质量筛选和缺失项提示可用。

### 7.1 阶段 138/140 真实闭环后续执行

服务器 readiness 已于 2026-05-15 通过。阶段 139/139.1 部署烟测后继续跑 C1/C2/C3 三个真实案例，人工跑测和 CSV 回填完成后执行：

```bash
python scripts/validate_stage138_closed_loop.py
bash scripts/stage138_server_closed_loop_verify.sh
```

如果失败，只处理第一条真实失败日志或第一条 CSV 缺口，不新增功能绕开。

### 7.2 本轮提交后立刻做

```bash
cd /opt/apps/ai-interview
git fetch origin
git reset --hard origin/main
docker compose up -d --build app admin frontend
docker compose exec app alembic upgrade head
docker compose exec app python -m app.scripts.check_database_capacity
```

### 7.3 后台管理员验收

1. 登录 `autsky6666@gmail.com`。
2. 打开“管理员管理”。
3. 新增普通管理员，确认普通管理员看不到管理员管理。
4. 新增带管理员管理权限的管理员，确认不能操作 root 保护项。
5. 打开“账号设置”，修改当前密码并重新登录。

### 7.4 简历解析验收

1. 上传 `2590603008詹已誉简历.pdf`。
2. 检查解析质量卡片是否显示。
3. 检查后端 `analysis.parse_quality`、`analysis.normalized_resume`。
4. 点击开始面试，确认不闪退。
5. 如果失败，只查第一条后端日志。

### 7.5 数据库并发治理验收

1. 执行 `check_database_capacity`。
2. 如果连接数接近上限，先降：
   - `UVICORN_WORKERS`
   - `DB_POOL_SIZE`
   - `DB_MAX_OVERFLOW`
3. 不要先迁移 MySQL。
4. 若后续真实用户持续增加，再评估 PgBouncer 或云数据库。

### 7.6 三岗位真实闭环

按 `docs/competition/三岗位真实闭环验收执行包.md`：

- C1：Python 后端开发工程师。
- C2：产品助理/产品经理实习生。
- C3：人力资源专员。

每个案例记录：

- 能力诊断。
- 简历润色。
- 学习任务。
- 至少 3 轮 AI 面试。
- 报告。
- 训练复盘。
- 后台案例标注人工评分。

## 8. 推荐精准暂存文件

阶段 139.1 收口只应暂存本轮相关文件，不暂存 PPT、申报书大文件、临时目录或未跟踪资料：

```powershell
git add ai-interview-admin/src/views/InterviewDetail.vue
git add "docs/competition/职启智评项目升级流程手册.md"
git add "docs/competition/三岗位真实闭环验收执行包.md"
git add "docs/competition/真实案例闭环验收记录.md"
git add "任务记录文档.md"
git add PROJECT_MEMORY.md
```

明确不暂存：

- `docs/competition/申报书/final/职启智评_人工智能创新赛答辩PPT_正式版.pptx`
- `docs/competition/职启智评初赛答辩演示.pptx` 的删除状态
- `.codex_tmp_*`
- 申报书 final 下的 docx/pdf/rar 等大文件
- `docs/paper/` 和成员原始资料

## 9. 本轮推荐提交信息

```powershell
git commit -m "chore: close stage 139 readiness gaps"
```
## 2026-05-17 阶段 166.3：个人模式隐私授权 UI 极简化与默认开启

- 当前最高优先级按用户明确指令执行：注册页、新建面试/上传简历、开始面试、简历润色、训练复盘、个人设置的用户端隐私授权 UI 收口为个人模式。
- 前端只保留截图式基础隐私与数据使用确认块：标题、核心处理说明、隐私协议链接、一个 checkbox；基础隐私协议与可选数据贡献授权均默认开启并随请求提交。
- 简历润色页不再显示隐私授权块，但润色上传请求默认带 `privacyAgreed=true`、`dataContributionConsent=true`。
- 训练复盘页删除本次案例数据贡献计划卡片；个人设置页删除数据贡献长说明、授权/撤回时间和单独撤回入口。
- 本轮只改用户端前端 UI 和提交默认值，不改后端数据库、后台导出门禁、隐私协议正文或训练样本准入规则。
