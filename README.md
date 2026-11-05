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

2026-11-05，Windows / Node.js 环境：用户端和管理端均通过 `npm ci --ignore-scripts --no-audit --no-fund` 与 `npm run build`。

首次检查后端测试为 285 项通过、1 项失败。后续修复了反馈接口缺少基础隐私同意检查的问题，并扩展 HTTP 回归测试，当前 **287 项全部通过**（包含新增的管理员身份配置回归测试）。依赖检查通过，Alembic 迁移链只有一个 head。实际改动见[本次开发记录](docs/development/2026-11-05-feedback-consent.md)，具体限制见[可行性报告](docs/chuanzhi-feasibility-2026-11-05.md)。这些检查不代表真实模型效果、生产部署或整条用户流程已经通过验收。

## 本地构建

分别进入两个前端目录执行：

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run build
```

后端使用 Python 3.12。建立独立虚拟环境后，安装 `ai-interview-backend/requirements-test.txt`，在后端目录执行 `python -m pytest -q`。

完整服务需要 PostgreSQL、Redis、数据库迁移和配置文件；AI 业务还要求用户在个人中心保存可用的模型 API Key。两个前端开发代理默认对齐后端端口 `8001`，可用 `VITE_DEV_PROXY_TARGET` 覆盖。

已提供根目录和双前端的 `.env.example`、独立单机编排 `compose.single-host.yml`，以及自动生成私有配置、初始化管理员和检查服务的工具。完整步骤见[腾讯云单机运行指南](docs/deployment/tencent-single-host.md)。单机预览通过 SSH 隧道访问，无需原作者的共享网关。原有 `docker-compose.yml` 仍用于共享网关生产拓扑。

## 云端部署状态

仓库已补充单机预览配置；实际云端部署状态以对应版本的验收记录为准。当前说明不表示真实模型流程或公网生产部署已经通过验收。

## 参考

- [第九届 AI WEB 网页开发挑战赛官网](https://www.boxuegu.com/matchTrack/detail/?id=10037)
- [详细可行性报告](docs/chuanzhi-feasibility-2026-11-05.md)
