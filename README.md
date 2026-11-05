# AI 面试项目 · 传智杯评估仓库

这是一个包含 Vue 3 用户端、Vue 3 管理端和 FastAPI 后端的 AI 面试与求职能力评估项目。目前用于第九届传智杯 **AI WEB 网页开发挑战赛（团队赛）** 的可行性评估。

## 项目组成

| 目录 | 内容 |
| --- | --- |
| `ai-interview-frontend/` | Vue 3 用户端：简历、面试、报告、学习任务等页面 |
| `ai-interview-admin/` | Vue 3 管理端 |
| `ai-interview-backend/` | FastAPI、SQLAlchemy、Alembic、Celery 等后端代码及测试 |
| `portal/` | 项目入口静态页面 |
| `docker-compose.yml` | PostgreSQL、Redis、后端及前端等生产编排 |
| `docs/competition/` | 原作者已有的比赛资料；不能作为本团队成果直接提交 |

## 已验证与限制

2026-11-05，Windows / Node.js 环境：用户端和管理端均通过 `npm ci --ignore-scripts --no-audit --no-fund` 与 `npm run build`。

首次检查后端测试为 285 项通过、1 项失败。后续修复了反馈接口缺少基础隐私同意检查的问题，并扩展 HTTP 回归测试，当前 **286 项全部通过**。依赖检查通过，Alembic 迁移链只有一个 head。实际改动见[本次开发记录](docs/development/2026-11-05-feedback-consent.md)，具体限制见[可行性报告](docs/chuanzhi-feasibility-2026-11-05.md)。这些检查不代表真实模型效果、生产部署或整条用户流程已经通过验收。

## 本地构建

分别进入两个前端目录执行：

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run build
```

后端使用 Python 3.12。建立独立虚拟环境后，安装 `ai-interview-backend/requirements-test.txt`，在后端目录执行 `python -m pytest -q`。

完整服务需要 PostgreSQL、Redis、数据库迁移和配置文件；AI 业务还要求用户在个人中心保存可用的模型 API Key。前端开发代理默认端口 `8006` 与后端默认端口 `8001` 不同，本地联调时应显式配置 `VITE_DEV_PROXY_TARGET=http://127.0.0.1:8001`。

当前没有随代码提供 `.env.example`，因此本页不承诺一键复现。生产配置及共享网关需按实际环境准备，不能照搬原作者的服务器参数。

## 云端部署状态

尚未执行云端部署，也未采购云资源、配置域名或调用付费模型。部署前先向项目持有人说明服务器、域名、API 费用和部署方案，待其确认后执行。

## 参考

- [第九届 AI WEB 网页开发挑战赛官网](https://www.boxuegu.com/matchTrack/detail/?id=10037)
- [详细可行性报告](docs/chuanzhi-feasibility-2026-11-05.md)
