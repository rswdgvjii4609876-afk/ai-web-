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
- `node_modules`、`dist`、`.vite-build-check` 是否被忽略

如果只是想跳过某一类检查，可用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -SkipPytest
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -SkipFrontendBuild
powershell -ExecutionPolicy Bypass -File scripts\stage79_local_preflight.ps1 -SkipAdminBuild
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
git reset --hard origin/main
bash scripts/stage79_server_verify.sh --deploy
```

脚本会执行：

- 拉取并重置到 `origin/main`。
- 重建 `app`、`frontend`、`admin`。
- 执行 Alembic 迁移。
- 初始化公共岗位画像。
- 检查后端健康接口、用户端、后台端、公共岗位画像数量和知识切片数量。
- 输出最近 300 行后端日志中的关键错误。

如果只想检查当前服务器，不拉代码、不重建：

```bash
cd /opt/apps/ai-interview
bash scripts/stage79_server_verify.sh
```

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
curl -fsS http://127.0.0.1:18001/api/v1/demo/competition
```

浏览器检查：

- 用户端工作台
- 参赛演示页
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
