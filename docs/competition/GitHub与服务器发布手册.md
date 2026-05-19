# GitHub 与服务器发布手册

本项目保留原仓库和服务器目录：

- 本地目录：`D:\apps\ai-interview`
- GitHub 仓库：`YiyuZh/ai-interview`
- 服务器目录：`/opt/apps/ai-interview`

## 1. 本地提交前检查

推荐使用一键本地预检脚本：

```powershell
cd D:\apps\ai-interview
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1
```

脚本会检查：

- `git diff --check`
- 后端 `python -m compileall app`
- 后端关键测试
- 用户端临时构建
- 后台端临时构建
- 真实闭环 CSV 结构
- 可选检查真实闭环 CSV 严格验收门槛
- 可选检查服务器验收报告
- `node_modules`、`dist`、`.vite-build-check` 是否被忽略

如果只是想跳过某一类检查，可用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -SkipPytest
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -SkipFrontendBuild
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -SkipAdminBuild
```

真实案例、人工评分和重复运行补齐后，可以把严格验收也纳入本地预检：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -StrictClosedLoopRecords
```

如需临时调整门槛：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -StrictClosedLoopRecords -MinCases 5 -MinCompleteFlows 5 -MinHumanScoredRows 5 -MinRepeatedCases 1
```

服务器报告回收后，可以把报告也纳入本地预检：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -ValidateServerReport
```

如果报告不是默认路径，指定文件：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -ValidateServerReport -ServerReportPath docs\competition\server_validation_reports\20260510_120000_stage79.md
```

手动检查仍可使用：

```powershell
cd D:\apps\ai-interview
git status --short
```

确认不要把临时构建目录、`.env`、日志或上传文件提交。

## 2. 构建检查

用户端：

```powershell
cd D:\apps\ai-interview\ai-interview-frontend
npm run build -- --outDir .vite-build-check
```

后台端：

```powershell
cd D:\apps\ai-interview\ai-interview-admin
npm run build -- --outDir .vite-build-check
```

## 3. 提交到 GitHub

```powershell
cd D:\apps\ai-interview
git add .gitignore docs/competition ai-interview-frontend ai-interview-admin ai-interview-backend
git commit -m "feat: adapt ai interview for zhiqi competition demo"
git push origin main
```

注意：当前仓库历史中已有 `dist` 和 `node_modules` 跟踪问题，本次不处理。后续可单独执行仓库瘦身。

## 4. 云服务器部署

推荐先使用阶段 79/81 的自动验收脚本：

```bash
cd /opt/apps/ai-interview
git fetch origin
git pull --ff-only
bash scripts/stage138_server_closed_loop_verify.sh --deploy --readiness-only
```

说明：生产发布默认使用阶段 138 验收脚本。`stage79_server_verify.sh` 只作为旧脚本保留，不再推荐用于生产发布；发布手册不再使用 `git reset --hard`，避免误删服务器未备份文件。

脚本会执行：

- 拉取并重置到 `origin/main`。
- 重建 `app`、`frontend`、`admin`。
- 执行 Alembic 迁移。
- 初始化公共岗位画像。
- 检查后端健康接口、用户端、后台端、公共岗位画像数量和知识切片数量。
- 输出最近 300 行后端日志中的关键错误。
- 生成服务器验收 Markdown 报告，默认路径：`docs/competition/server_validation_reports/stage79_server_verify_latest.md`。

如果只想检查当前服务器，不拉代码、不重建：

```bash
cd /opt/apps/ai-interview
bash scripts/stage138_server_closed_loop_verify.sh --readiness-only
```

如果要把报告写到指定位置：

```bash
bash scripts/stage138_server_closed_loop_verify.sh --deploy --readiness-only --report docs/competition/server_validation_reports/$(date +%Y%m%d_%H%M%S)_stage138.md
```

报告中会记录：执行前后提交、公共岗位画像数量、知识切片数量、HTTP 检查结果、最近后端关键日志和人工验收入口。若脚本返回 `FAIL`，先处理报告里第一条失败项。

把服务器报告拉回本地或直接在服务器上检查时，使用：

```bash
python scripts/validate_server_validation_report.py --report docs/competition/server_validation_reports/stage79_server_verify_latest.md
```

看到 `result=PASS` 后，再进入真实简历闭环验收；如果输出 `ERROR`，先处理第一条错误。

手动部署命令仍可使用：

```bash
cd /opt/apps/ai-interview
git pull
docker compose up -d --build
```

如只改前端和后台，可按实际服务名单独构建；如果不确定，使用完整构建更稳。

## 5. 初始化公共岗位画像

```bash
docker compose exec app python -m app.scripts.seed_competition_knowledge_bases
```

如果服务器服务名不是 `app`，先执行：

```bash
docker compose ps
```

再替换为实际后端容器服务名。

## 6. 部署后检查

```bash
curl -fsS http://127.0.0.1:18001/api/v1/config/health
curl -fsS http://127.0.0.1:18001/api/v1/competition/demo-cases
curl -fsS http://127.0.0.1:18001/api/v1/competition/sft-preview
```

浏览器检查：

- 用户端工作台
- 参赛演示页：`/competition/agent-trace`，旧 `/competition-demo` 仅保留兼容跳转
- 简历测评页
- 岗位画像库
- 后台公共岗位画像
- 后台评测样本

## 7. 后续仓库瘦身

参赛功能稳定后，再单独处理：

```powershell
git rm -r --cached ai-interview-frontend/node_modules ai-interview-admin/node_modules
git rm -r --cached ai-interview-frontend/dist ai-interview-admin/dist
git commit -m "chore: stop tracking generated frontend artifacts"
git push origin main
```

执行前必须先确认云服务器部署方式仍然通过 Docker 构建源码，而不是直接读取仓库里的 `dist`。
