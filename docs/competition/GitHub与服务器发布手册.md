# GitHub 与服务器发布手册

本项目保留原仓库和服务器目录：

- 本地目录：`D:\apps\ai-interview`
- GitHub 仓库：`YiyuZh/ai-interview`
- 服务器目录：`/opt/apps/ai-interview`

## 1. 本地提交前检查

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
