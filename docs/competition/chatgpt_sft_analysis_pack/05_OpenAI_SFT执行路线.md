# OpenAI SFT 执行路线

## 1. 总体流程

```text
本地推送最新代码
-> 服务器拉取并重建容器
-> 配置官方 OpenAI Key 和可微调 base model
-> 准备真实授权样本
-> dry-run 生成训练集
-> 付费前 dry-run 创建检查
-> 创建 OpenAI fine-tuning job
-> 查询训练状态
-> 拿到 fine_tuned_model
-> 用 holdout 做 base/fine-tuned 对比
-> 形成答辩材料
```

## 2. 本地推送

当前本地 `main` 领先远端 16 个提交。服务器开跑前需要先推送：

```bash
cd D:\apps\ai-interview
git push origin main
```

意义：

- 让服务器能拉到阶段 144 的 OpenAI SFT 脚本。
- 避免服务器报 `No module named app.scripts.prepare_openai_fine_tuning_dataset`。

## 3. 服务器更新

```bash
cd /opt/apps/ai-interview
git pull
git log --oneline -3
docker compose up -d --build
docker compose exec -T app alembic upgrade head
```

检查：

```bash
docker compose ps
curl -fsS http://127.0.0.1:18001/api/v1/config/health
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset --help
```

通过标准：

- app、postgres、redis 健康。
- health 返回 database 和 redis 都是 up。
- SFT 脚本 help 能正常输出。

## 4. 配置 OpenAI

服务器 `.env` 需要配置：

```env
OPENAI_API_KEY=<官方 OpenAI API Key>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_FINE_TUNE_BASE_MODEL=<当前账号支持 fine-tuning 的模型 ID>
OPENAI_FINE_TUNE_SUFFIX=zhiqi-sft
```

安全要求：

- 不把 Key 写进仓库。
- 不截图暴露 Key。
- 不用来源不明的中转 Key 做正式训练。
- base model 以 OpenAI 控制台或官方文档当前支持列表为准。

## 5. 生成训练集 dry-run

```bash
cd /opt/apps/ai-interview
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset \
  --dry-run \
  --output-dir "$DATASET_DIR"
```

重点看：

```text
ready_for_openai_job
real_authorized_samples
constructed_samples
train_samples
validation_samples
blockers
```

如果 `ready_for_openai_job=False`，继续补真实授权样本和后台人工评分。

## 6. 创建 job 前预检

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job \
  --dry-run \
  --dataset-dir "$DATASET_DIR"
```

意义：

- 检查训练集是否存在。
- 检查 `summary.json` 是否 ready。
- 检查 base model 配置。
- 不上传文件，不产生费用。

## 7. 创建真实 OpenAI job

只有预检通过后才执行：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job \
  --confirm-cost \
  --dataset-dir "$DATASET_DIR"
```

成功后应生成：

```text
job_record.json
```

之后不要重复创建 job，默认只查状态。

## 8. 查询状态

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.check_openai_fine_tuning_job \
  --dataset-dir "$DATASET_DIR"
```

如果状态是 `running`，每隔 5-10 分钟查询一次。

如果状态是 `failed`，先看 `job_status.json` 的第一条失败原因，不新增功能绕开。

如果状态是 `succeeded` 且有 `fine_tuned_model`，进入 eval。

## 9. Eval 对比

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.run_fine_tuning_eval \
  --confirm-cost \
  --dataset-dir "$DATASET_DIR"
```

如果提示验证集不足，继续补样本，不降低标准。

