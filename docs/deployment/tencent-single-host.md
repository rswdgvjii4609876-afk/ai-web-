# 腾讯云单机运行指南

适用：Linux 单机、Docker Engine 和 Compose 插件。为 2 核 2GB 的测试环境提供低并发起点；实际容量需要部署后测量。默认后端 1 进程、Celery solo 1 进程，镜像串行构建。PostgreSQL 和 Redis 不发布主机端口。

## 无域名时的访问方式

`compose.single-host.yml` 独立创建网络和数据卷，不需要原作者的 `shared_gateway`。默认使用 preview 环境，两个 Web 入口只绑定服务器的 `127.0.0.1:8080/8081`，通过 SSH 隧道访问。此方式不需要为 8080/8081 开放腾讯云防火墙，也不会在公网 HTTP 上传输登录口令或模型 Key。

保持 22 端口对你的登录来源可达。腾讯云轻量实例防火墙和操作系统防火墙是两层独立规则，参见[官方说明](https://cloud.tencent.com/document/product/1207/44577)。配置本身不会修改云端防火墙。

## 服务器准备

先记录系统和已有服务：

```bash
cat /etc/os-release
free -h
df -h /
ss -lnt
docker version
docker compose version
```

如尚无 Docker，按对应系统的 [Docker Engine 官方安装文档](https://docs.docker.com/engine/install/)安装 Engine 和 Compose 插件。不要为安装而重装已有服务器。2GB 主机构建前应留出可用内存及磁盘；内存不足时可以在确认现有 swap 和磁盘后配置 swap，或在更大的构建机生成镜像。

将私有仓库克隆或将已审查的源码包上传到一个新的项目目录。认证仅用于取得私有代码，部署目录不应保存 GitHub 访问令牌。已有业务目录不要覆盖。

## 生成配置和启动

在仓库根目录执行：

```bash
python3 scripts/init_runtime_env.py --admin-email YOUR_EMAIL
bash scripts/run_single_host.sh
```

生成器创建权限为 600 的 `.env`，自动生成数据库密码、Redis 密码、JWT 密钥和个人模型凭据加密密钥。它拒绝覆盖现有文件，且不会打印秘密值。模板 `.env.example` 可以提交，真实 `.env` 必须保留在部署主机并纳入私有备份。

数据库迁移作为一次性服务执行，API 等待迁移成功及 Redis 健康后启动。用户端和管理端等待 API 健康。就绪端点会检查 API、数据库、Redis 和 Alembic 版本。[Compose 启动依赖说明](https://docs.docker.com/compose/how-tos/startup-order/)。

首次创建管理员：

```bash
docker compose -f compose.single-host.yml exec app python scripts/bootstrap_admin.py
```

交互输入初始密码并确认，至少 12 位且包含字母、数字、特殊字符。管理员身份取自 `.env` 中 `ROOT_ADMIN_EMAIL`；新安装无需使用原作者邮箱。脚本不会把初始密码保存在 `.env` 或打印出来。已有同邮箱账号不会被覆盖或自动提权。

根目录 `.env` 专用于这个 Compose 方案，不要复制到后端源码目录：其中包含 Compose 专用变量，直接作为 Pydantic 的 dotenv 文件读取会出现额外字段错误。容器通过环境变量接收这些值。

## 在本机打开应用

在自己的电脑执行以下命令，替换 SSH 用户名和服务器 IP，保持连接开启：

```bash
ssh -N -L 8080:127.0.0.1:8080 -L 8081:127.0.0.1:8081 USER@SERVER_IP
```

用户端：`http://localhost:8080`；管理端：`http://localhost:8081`。

普通用户注册、同意隐私协议后，在个人中心保存自己的模型 API Key，再验收简历、面试和报告。服务启动成功不表示真实模型已验证，也不会自动产生付费模型调用。当前模板的模型名沿用项目支持列表，实际使用前以供应商账号可用模型为准。

## 检查、日志和备份

```bash
python3 scripts/check_runtime.py
docker compose -f compose.single-host.yml ps
docker compose -f compose.single-host.yml logs --tail=100 app migrate celery-worker
docker stats --no-stream
```

`check_runtime.py` 检查两个前端和四项后端就绪状态；失败时退出码为 1，可由监控或定时任务捕获。日志滚动上限为每容器 3 个 10MB 文件。容器异常退出后自动重启，健康检查失败会显示 unhealthy；仅变为 unhealthy 不会自动重启容器。

在低写入时段执行：

```bash
bash scripts/backup_single_host.sh
```

备份包括数据库 dump、上传文件、`.env` 和 Git 版本，放在被忽略的 `backups/` 下。数据库快照与上传文件不是跨资源原子快照；需要严格一致时先停止用户写入。备份包含个人数据和加密密钥，不能提交 Git。应另外保存到持有人控制的位置。

更新前先备份并记录 `git rev-parse HEAD`。回退应用时先核对数据库迁移是否向后兼容，再检出上一版并串行重建。涉及不兼容迁移时，应在维护窗口从对应备份恢复，不自动执行数据库降级或清空卷。不要使用 `docker compose down -v`，该命令会删除持久化数据。

Celery Beat 的定时示例默认不启动；需要项目定时队列时使用 `docker compose -f compose.single-host.yml --profile scheduler up -d --no-build`。后台任务繁忙时 solo worker 的远程 ping 可能暂时不响应，需结合任务日志判断。

## 后续公开演示

当前方案用于通过 SSH 隧道验收。公开演示需要单独配置 HTTPS 入口、访问来源、演示账号及模型额度；可复用现有生产方案或配置独立反向代理。切换 `ENV=production` 前必须填写真实前端 URL、显式 CORS 和现有生产校验要求的服务端模型 Key。不要用随机字符串充当真实模型 Key 来绕过校验。

## 前端源码开发

两个前端目录均提供 `.env.example`，可复制为各自 `.env.local`。默认开发代理已对齐后端的 8001 端口。如果使用本指南容器里的 API，可把开发代理目标改成 `http://127.0.0.1:8080`，经用户端 Nginx 转发 API。

本指南不代表已完成云端部署、真实业务验收或压力测试。部署结果应另存包含提交版本、系统信息和检查结果的记录。
