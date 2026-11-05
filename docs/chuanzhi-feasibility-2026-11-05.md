# 第九届传智杯 AI WEB 项目可行性评估

评估日期：2026-11-05（北京时间）。

目标赛道：第九届 AI WEB 网页开发挑战赛，团队赛。

## 判断

AI 面试与求职训练的 Web 应用方向与赛道相符。现有项目具备继续评估和开发的技术基础，但当前版本不宜直接作为本团队原创成品提交。

项目持有人已说明，原作者朋友赠送了项目，但不加入团队。按已获授权继续处理代码使用与开发，不再将“缺少公开许可证”本身当作用户没有授权的证明。参赛原创性仍需单独核对：所有权转移不等于参赛队完成了原有开发，新增多少功能能被接受也没有可据此保证的统一比例。

较稳妥的路径是如实说明受让来源与已有功能，向组委会确认这种基础上的二次开发是否可接受，再以团队真实完成的核心功能、测试和开发过程作为成果。若该方式不被接受，可以独立实现自己的方案。

## 仓库状态

- 上游：[YiyuZh/ai-interview](https://github.com/YiyuZh/ai-interview)。
- 独立仓库：[rswdgvjii4609876-afk/ai-interview-chuanzhi](https://github.com/rswdgvjii4609876-afk/ai-interview-chuanzhi)，私有，`fork=false`。
- 导入基线：`3200645a046a515488b8b19d8d0fc19155dddede`，2026-10-19 的提交。
- 已保留基线及之前全部 127 次提交与作者信息；这些不是本团队的原创开发记录。
- 本地 `origin` 指向新仓库，`upstream` 指向原仓库。
- 首次评估仅增加项目说明和评估报告。后续真实修复了反馈接口的隐私同意检查，并补充 HTTP 回归覆盖，详见[开发记录](development/2026-11-05-feedback-consent.md)；原作者历史保持不变。
- 原仓库 GitHub 许可证字段为空，当前树未发现许可证文件。本次未添加新的代码许可证。

## 赛道核对

2026-11-05 从[赛道官网](https://www.boxuegu.com/matchTrack/detail/?id=10037)及其页面实际调用的[官方详情接口](https://gateway.boxuegu.com/portal-marketing/competition/track/detail?id=10037&includeDetail=true)读取规则。以下是摘要，具体以官网和学校通知为准。

| 项目 | 核对结果及影响 |
| --- | --- |
| 选题 | 允许自拟 AI Web 应用，AI 应是核心能力；面试训练方向可以匹配 AI 助手、教育学习等方向。这是对规则与项目功能的适配判断。 |
| 原创性 | 明确要求原创，禁止包装既有项目参赛。已获原作者授权并不自动满足这项要求。 |
| 组队 | 同校 1–3 名学生，最多 2 名指导教师；组别依学校与学籍情况选择。 |
| 仓库 | GitHub/Gitee，公开或给评审访问权限，保留真实 Git 历史，提供 README、环境模板及依赖说明。 |
| 视频 | 5–8 分钟、MP4、至少 1080p，包含功能和 AI 技术展示。 |
| 文档 | PDF，不超过 30 页，说明需求、架构、AI 方案、实现、测试部署和创新点。 |
| 在线演示 | 可选加分项；提供时要保持可用，登录系统需提供评审体验账号。 |
| 时间 | 页面列出报名及作品提交截止为 2026-11-18；校内选拔可能更早。页面也有后续反馈和最终提交安排，须查看报名后的个人中心及学校通知确认。 |
| 评分 | AI 技术深度 35%，创新性 25%；前端质量、实用性、体验、社会价值与商业潜力各 10%。 |

因此，不能只靠改名、换配色或导入朋友的提交历史来证明团队贡献。不要把历史开发过程重新署名为本团队开发。

## 代码导览

一句话：这是 Vue 3 双前端配合 FastAPI、PostgreSQL、Redis/Celery 的简历分析与模拟面试系统。

用户输入包括简历文件、目标岗位、面试回答和个人 AI 接口配置；输出包括简历分析、面试问题、流式评语、报告和训练任务。用户端入口位于 `ai-interview-frontend/src/router/index.js`，后台位于 `ai-interview-admin/`，后端入口为 `ai-interview-backend/main.py`。

已追踪的实际面试调用关系：

1. `ai-interview-frontend/src/api/interview.js` 请求 `/interviews/start` 和答题流式接口。
2. `ai-interview-backend/main.py` 调用 `app/route/route.py:create_app()`，路由由 `app/route/router_registry.py` 注册。
3. `app/api/client/v1/interview.py` 检查用户、隐私同意和个人模型配置。
4. `app/services/common/deepseek_config_service.py:build_runtime_config()` 在 `require_personal_key=True` 时要求用户已有可解密的个人 API Key。只配置服务器环境变量不足以直接体验当前用户 AI 流程。
5. `app/services/client/interview_service.py` 执行业务和数据库写入，通过 `app/services/client/ai_service.py` 调用模型生成问题、评价与报告。

上述路径确认的是代码实现，不代表真实模型接口和完整用户链路已实测通过。

## 演示与真实能力的边界

| 已检查内容 | 实际情况 |
| --- | --- |
| `app/services/agent_orchestrator/demo_pipeline.py` | 用演示样本和确定性逻辑组装带 Agent 名称的步骤；该文件不能证明自主多 Agent 已实际运行。 |
| `app/services/agent_orchestrator/evaluator.py` | 预览基线分数固定，其他分数由关键词等规则计算；不是独立测试集上的真实模型对比。 |
| `app/services/agent_orchestrator/sft_preview.py` | 生成预览样本，明确 `ready_for_real_training=False`，真实授权样本计数为 0。 |
| `docs/competition/opc/12_可展示成果与不能夸大边界.md` | 原作者也明确区分原型、预览、真实样本与微调完成状态。 |

仓库有另外的模型调用、微调操作代码和文档；本次没有发起训练、模型请求或验证任何微调作业完成状态。原作者的讲稿、PPT、评测与数据材料不能直接作为本团队的实验成果。

## 本次验证

| 检查 | 结果 |
| --- | --- |
| 用户端安装与生产构建 | 通过，`npm ci --ignore-scripts --no-audit --no-fund` + `npm run build`，142 个模块。 |
| 管理端安装与生产构建 | 通过，同上，113 个模块。 |
| 后端测试初次基线 | `python -m pytest -q --tb=short`：285 passed，1 failed，运行约 5.94 秒。 |
| 后端测试修复后 | 相同测试集扩展 HTTP 隐私门禁覆盖后，286 passed，约 3.43 秒。 |
| Python 依赖一致性 | `python -m pip check` 通过。 |
| Alembic 迁移链 | `python -m alembic heads` 返回唯一 head：`c719af032001`；未连接数据库执行迁移。 |
| Docker 构建及编排启动 | 未执行，本机未发现 Docker 命令。 |
| PostgreSQL/Redis/真实 AI 全流程 | 未验收；未启动服务基础设施，未配置真实模型凭据。 |
| 云端部署 | 未执行。 |

验证环境：Windows，Node.js 24.22.1，工作区独立 Python 3.12.14 虚拟环境；使用原项目测试依赖。测试时模型密钥设为占位值，未发起付费模型调用。前端成功构建说明代码可打包，不等于登录、上传、面试和报告全流程均可用。

初始失败项为 `tests/test_privacy_stage152_exposure.py::test_client_routes_do_not_bypass_base_privacy_gate`。检查发现 `app/api/client/v1/feedback.py` 的创建、列表和详情接口直接依赖 `get_current_user`，没有复用项目已有的基础隐私同意检查。反馈路由原有登录和用户归属限制，不能据此解释为允许匿名访问或读取他人反馈。

后续将三个接口接入 `require_base_privacy_consent`；HTTP 测试验证缺失或旧版同意会被拒绝、当前版本同意后可操作，并继续验证登录要求、用户数据隔离及后台回复权限。扩展后的 HTTP 测试在修复前失败（实际 200、预期 400），修复后全部 286 项测试通过。这是本次实际完成的工程维护贡献，不替代赛事对原创性的判断。

## 复现与部署准备

已发现的具体环境依赖：

- 根 `docker-compose.yml` 需要 `.env`，但仓库没有环境模板；`.gitignore` 还忽略了 `.env.example` 等示例文件。
- 配置依赖 PostgreSQL 16、Redis 7、Alembic 迁移及 Celery。默认生产校验要求显式域名/CORS、有效密钥和数据库/Redis 配置。
- 根编排引用一个外部 `shared_gateway` 网络，原文档基于原作者已有 Caddy 网关与其他项目共存；在新服务器不能直接假设这些资源存在。
- 本地 Vite 代理默认 `127.0.0.1:8006`，后端默认端口是 `8001`，联调需显式对齐。
- 当前 AI 用户流程要求个人中心配置模型 Key。评审体验账号和 API 额度需要提前规划。
- 原作者部署文档包含其既有路径和服务背景，需针对本项目的新环境整理。

若后续决定上云，拟使用 Linux 主机与 Docker Compose，配合 HTTPS 反向代理、持久化存储和备份。服务器规格、服务商、区域、域名和模型费用需选型及实测后核算，本报告不把未核验的估价当作报价。

**部署前先向项目持有人说明方案与费用，确认后才执行。当前未采购资源、连接原作者服务器、发布站点、变更 DNS 或调用付费 AI。**

## 面向本团队的开发建议

以下是建议，尚未实施：

1. 先向组委会说明“原作者赠送，原作者不参赛，团队基于此继续开发”，确认允许范围；保留来源与授权记录。
2. 用实际需求调研确定独立创新点，例如针对某专业岗位的证据追问、可追溯评分和训练前后变化，避免把原仓库已有能力再次写成新增创新。
3. 实现选定功能、采集获授权的测试数据并完成真实验证，按实际开发过程提交代码，记录 AI 辅助使用情况。
4. 补齐可复现配置与本团队材料；演示与实验数据分别注明来源和性质。
5. 本地完成“注册/登录 → 简历上传 → 面试 → 报告 → 训练复盘”验收，再讨论是否为可选演示加分项部署云端。

## 依据及范围

- [原始仓库](https://github.com/YiyuZh/ai-interview)：基线版本如上，仅对实际读取的配置、路由、服务片段、演示实现和相关测试作判断。
- [AI WEB 赛道官网](https://www.boxuegu.com/matchTrack/detail/?id=10037)及[详情接口](https://gateway.boxuegu.com/portal-marketing/competition/track/detail?id=10037&includeDetail=true)：本次赛道规则依据。
- [GitHub 关于仓库许可的说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)：公开可见不自动授予任意再利用权；用户另行获得原作者授权的情况应另行判断。

本报告是初步工程与规则适配评估，不是组委会对参赛资格或原创性的确认，也未完成全仓库审计、生产压测或实际模型效果评估。
