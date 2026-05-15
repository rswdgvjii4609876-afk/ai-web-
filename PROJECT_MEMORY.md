# PROJECT_MEMORY.md

更新时间：2026-05-15

项目目录：`D:\apps\ai-interview`  
服务器目录：`/opt/apps/ai-interview`  
GitHub 仓库：`YiyuZh/ai-interview`  
主控文档：`docs/competition/职启智评项目升级流程手册.md`  
详细历史：`任务记录文档.md`

## 1. 当前正在实现的功能目标

当前项目主线不是单纯“AI 面试官”，而是“就业能力诊断与提升平台”：

`简历解析 -> 目标岗位 -> 岗位画像/岗位知识库 -> 简历证据评分 -> 能力差距诊断 -> 学习任务 -> AI 模拟面试 -> 报告 -> 训练复盘 -> 人工评分沉淀`

最近正在收口的重点：

1. 后台管理员账号和权限管理。
2. 简历 PDF 解析兼容性和开始面试稳定性。
3. PostgreSQL 并发治理和数据库容量自检。
4. 核心链路自动自检，为后续三岗位真实闭环验收做准备。
5. 阶段 138 服务器真实闭环验收和 C1/C2/C3 人工评分数据沉淀。

当前策略：

- 保留 PostgreSQL，不迁移 MySQL。
- 成员资料不再作为新岗位画像，而是归并到已有标准岗位画像。
- 简历评分、润色、学习计划、AI 面试、报告和复盘要统一使用简历评价快照和证据状态。
- 服务器真实验收和 C1/C2/C3 三岗位闭环仍待补，不要把本地通过写成线上完成。

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
- 每条真实案例必须覆盖：上传简历、能力诊断、简历润色、学习任务、至少 3 轮面试、报告、训练复盘、后台人工评分。
- `--readiness-only` 可用于人工跑测前的服务器预检，此时 C1/C2/C3 未完成只记为 WARN。
- 完整模式下，CSV 未达到阶段 138 口径会返回 FAIL。

当前状态：

- 阶段 138 工具和文档口径已落地。
- 2026-05-15 服务器 commit `b42cff1` 已执行 `bash scripts/stage138_server_closed_loop_verify.sh --readiness-only`，结论为 `WARN`。
- 该 WARN 只来自 C1/C2/C3 尚未跑测；服务器 readiness 关键项已通过：Alembic、健康检查、PostgreSQL 容量、阶段 133 核心自检、root 管理员权限、关键日志扫描。
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

### 4.3 文档和流程

- `docs/competition/职启智评项目升级流程手册.md`
  - 当前主控路线。
  - 已追加阶段 135、136、137、138。

- `docs/competition/三岗位真实闭环验收执行包.md`
  - 阶段 138 C1/C2/C3 执行入口。

- `docs/competition/真实案例闭环验收记录.md`
  - 阶段 138 记录和机器检查口径。

- `scripts/stage138_server_closed_loop_verify.sh`
  - 服务器 readiness 和闭环验收报告脚本。

- `scripts/validate_stage138_closed_loop.py`
  - C1/C2/C3 真实闭环 CSV 检查脚本。

- `任务记录文档.md`
  - 长历史记录。
  - 已追加阶段 135、136、137、138。

## 5. 当前未完成事项

1. 阶段 138 三岗位真实闭环和数据沉淀：
   - 服务器 readiness 已通过；当前只剩 C1/C2/C3 真实案例未跑测。
   - 按执行包跑 C1/C2/C3。
   - 每个案例补齐诊断、润色、学习任务、至少 3 轮面试、报告、训练复盘和后台人工评分。
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

### 7.0 阶段 138 优先执行

服务器 readiness 已于 2026-05-15 通过，当前直接跑 C1/C2/C3 三个真实案例。人工跑测和 CSV 回填完成后执行：

```bash
python scripts/validate_stage138_closed_loop.py
bash scripts/stage138_server_closed_loop_verify.sh
```

如果失败，只处理第一条真实失败日志或第一条 CSV 缺口，不新增功能绕开。

### 7.1 本轮提交后立刻做

```bash
cd /opt/apps/ai-interview
git fetch origin
git reset --hard origin/main
docker compose up -d --build app admin frontend
docker compose exec app alembic upgrade head
docker compose exec app python -m app.scripts.check_database_capacity
```

### 7.2 后台管理员验收

1. 登录 `autsky6666@gmail.com`。
2. 打开“管理员管理”。
3. 新增普通管理员，确认普通管理员看不到管理员管理。
4. 新增带管理员管理权限的管理员，确认不能操作 root 保护项。
5. 打开“账号设置”，修改当前密码并重新登录。

### 7.3 简历解析验收

1. 上传 `2590603008詹已誉简历.pdf`。
2. 检查解析质量卡片是否显示。
3. 检查后端 `analysis.parse_quality`、`analysis.normalized_resume`。
4. 点击开始面试，确认不闪退。
5. 如果失败，只查第一条后端日志。

### 7.4 数据库并发治理验收

1. 执行 `check_database_capacity`。
2. 如果连接数接近上限，先降：
   - `UVICORN_WORKERS`
   - `DB_POOL_SIZE`
   - `DB_MAX_OVERFLOW`
3. 不要先迁移 MySQL。
4. 若后续真实用户持续增加，再评估 PgBouncer 或云数据库。

### 7.5 三岗位真实闭环

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

本轮计划暂存代码和记忆，不暂存临时目录和申报材料大文件：

```powershell
git add .env.example
git add ai-interview-backend/.env.example
git add ai-interview-backend/Dockerfile
git add ai-interview-backend/Dockerfile.dev
git add ai-interview-backend/requirements.txt
git add ai-interview-backend/app/core/config.py
git add ai-interview-backend/app/db/base.py
git add ai-interview-backend/app/api/backoffice/v1/admin.py
git add ai-interview-backend/app/models/admin.py
git add ai-interview-backend/app/schemas/backoffice/admin.py
git add ai-interview-backend/app/schemas/backoffice/auth.py
git add ai-interview-backend/app/scripts/seed_admin.py
git add ai-interview-backend/app/services/backoffice/admin.py
git add ai-interview-backend/scripts/create_first_admin.py
git add ai-interview-backend/migrations/versions/a2c4e6f8b135_add_admin_management_permission.py
git add ai-interview-backend/tests/test_admin_permissions.py
git add ai-interview-admin/src/App.vue
git add ai-interview-admin/src/api/index.js
git add ai-interview-admin/src/router/index.js
git add ai-interview-admin/src/stores/auth.js
git add ai-interview-admin/src/views/Login.vue
git add ai-interview-admin/src/views/Admins.vue
git add ai-interview-admin/src/views/AccountSettings.vue
git add ai-interview-backend/app/services/client/resume_service.py
git add ai-interview-backend/app/services/client/interview_service.py
git add ai-interview-backend/app/services/client/resume_text_extractor.py
git add ai-interview-backend/app/services/client/resume_normalizer.py
git add ai-interview-backend/tests/test_resume_text_extractor.py
git add ai-interview-backend/tests/test_resume_normalizer.py
git add ai-interview-frontend/src/views/ResumeUpload.vue
git add ai-interview-backend/app/scripts/check_core_feature_flow.py
git add ai-interview-backend/tests/test_check_core_feature_flow.py
git add ai-interview-backend/app/scripts/check_database_capacity.py
git add scripts/stage79_local_preflight.ps1
git add scripts/validate_stage138_closed_loop.py
git add scripts/stage138_server_closed_loop_verify.sh
git add "docs/competition/职启智评项目升级流程手册.md"
git add "docs/competition/三岗位真实闭环验收执行包.md"
git add "docs/competition/真实案例闭环验收记录.md"
git add "任务记录文档.md"
git add PROJECT_MEMORY.md
```

两个 tracked 删除项按用户确认纳入提交；用 `git status --short` 确认它们仍是 `D`。

## 9. 本轮推荐提交信息

```powershell
git commit -m "feat: improve admin, resume parsing, and database operations"
git push origin main
```
