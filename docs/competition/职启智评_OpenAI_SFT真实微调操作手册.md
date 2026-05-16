# 职启智评 OpenAI SFT 真实微调操作手册

更新时间：2026-05-16  
适用项目：`D:\apps\ai-interview`  
服务器目录：`/opt/apps/ai-interview`  
适用对象：会 SSH 登录服务器、会复制命令，但不熟悉 OpenAI fine-tuning 的操作者

## 1. 一句话判断：你现在能不能训练

先不要急着创建 OpenAI 微调任务。按下面判断：

| 当前情况 | 下一步 |
|---|---|
| 没有 3 条真实授权样本 | 先跑真实案例和后台人工评分 |
| 有样本，但 `ready_for_openai_job=False` | 看 `blockers`，补缺口 |
| `ready_for_openai_job=True` | 先跑付费前 dry-run |
| dry-run create 通过 | 再用 `--confirm-cost` 创建真实 job |
| job 还在 `running` | 只查状态，不重复创建 |
| job `succeeded` 且有 `fine_tuned_model` | 跑 eval 对比 |
| eval 提示验证集少于 5 条 | 补样本，不要降低标准 |

只有拿到 `fine_tuned_model` 后，答辩里才能说：

```text
已完成一次 OpenAI SFT 微调实验。
```

## 2. 开工前 5 分钟检查

### 2.1 确认本地提交已经推到 GitHub

如果代码只是本地 commit，服务器 `git pull` 拉不到。

本地检查：

```bash
git log --oneline -3
git status -sb
```

应能看到包含这些提交信息或更新版本：

```text
feat: add OpenAI SFT launch scripts
docs: clarify OpenAI SFT manual workflow
```

如果服务器需要从 GitHub 拉代码，先在本地推送：

```bash
git push origin main
```

意义：

- 保证服务器能拉到 OpenAI SFT 脚本和这份手册。
- 避免服务器执行后报 `No module named app.scripts.prepare_openai_fine_tuning_dataset`。

### 2.2 确认你有 OpenAI 正式训练条件

你需要具备：

- 官方 OpenAI API Key。
- OpenAI 账号已开通 billing。
- 当前账号有 fine-tuning 权限。
- 知道当前账号支持 fine-tuning 的 base model。

注意：

- 不要用中转 Key 做正式训练。
- 不要把 API Key 发到聊天窗口。
- 不要截图泄露 API Key。
- 不要把 `.env` 提交到 Git。

### 2.3 确认至少有 3 条真实授权案例

真实样本最低门槛：

```text
real_authorized_samples >= 3
train_samples >= 10
```

构造样本可以补数量，但不能替代真实样本。
如果 `real_authorized_samples=0`，只能说“脚本和格式准备好了”，不能说完成真实微调。

## 3. 服务器更新与脚本确认

登录服务器后执行：

```bash
cd /opt/apps/ai-interview
git pull
git log --oneline -3
```

意义：

- `git pull`：拉取阶段 144 的脚本和手册。
- `git log --oneline -3`：确认服务器确实更新到了包含 SFT 脚本的提交。

重新构建：

```bash
docker compose up -d --build
docker compose exec -T app alembic upgrade head
```

意义：

- `docker compose up -d --build`：让新增 Python 脚本进入 app 镜像。
- `alembic upgrade head`：确认数据库迁移是最新状态。

健康检查：

```bash
docker compose ps
curl -fsS http://127.0.0.1:18001/api/v1/config/health
```

期望：

- `ai-interview-app`、`ai-interview-postgres`、`ai-interview-redis` 是 healthy。
- health 接口返回 database 和 redis 都是 up。

确认脚本存在：

```bash
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset --help
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job --help
```

如果报 `No module named app.scripts...`：

- 服务器没拉到最新代码，回到 `git pull`。
- 或镜像没重建，重新跑 `docker compose up -d --build`。

构建很慢时：

- 不要手动删除数据库卷。
- 不要中断 postgres/redis 数据目录。
- 先确认 Dockerfile 仍使用清华 apt/pip 源。
- 可以只观察构建日志，确认卡在 apt、pip 还是前端构建。

## 4. OpenAI 配置与安全检查

编辑服务器 `.env`：

```bash
cd /opt/apps/ai-interview
nano .env
```

补齐或确认：

```env
OPENAI_API_KEY=<你的官方 OpenAI API Key>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_FINE_TUNE_BASE_MODEL=你当前账号支持的可微调模型ID
OPENAI_FINE_TUNE_SUFFIX=zhiqi-sft
```

每一项意义：

- `OPENAI_API_KEY`：上传训练文件、创建微调 job、查询状态和跑 eval。
- `OPENAI_BASE_URL`：正式微调使用 OpenAI 官方地址。
- `OPENAI_FINE_TUNE_BASE_MODEL`：当前账号支持 fine-tuning 的 base model。
- `OPENAI_FINE_TUNE_SUFFIX`：训练后模型名后缀，方便识别为职启智评实验。

配置建议：

- `OPENAI_FINE_TUNE_BASE_MODEL` 不在手册里写死，避免模型可用性变化。
- 以 OpenAI 控制台和官方 fine-tuning 页面当前显示为准。
- 如果真实创建 job 时报 “model does not support fine-tuning”，说明 base model 填错。

改完重启 app：

```bash
docker compose up -d --build app celery-worker celery-beat
```

意义：

- 让 app 容器重新读取 `.env`。
- celery 也同步读取最新环境变量。

安全检查环境变量，不打印 Key 全文：

```bash
docker compose exec -T app python - <<'PY'
import os
key = os.getenv("OPENAI_API_KEY", "")
print("OPENAI_API_KEY_SET=", bool(key and key != "your-openai-api-key"))
print("OPENAI_BASE_URL=", os.getenv("OPENAI_BASE_URL", ""))
print("OPENAI_FINE_TUNE_BASE_MODEL=", os.getenv("OPENAI_FINE_TUNE_BASE_MODEL", ""))
print("OPENAI_FINE_TUNE_SUFFIX=", os.getenv("OPENAI_FINE_TUNE_SUFFIX", ""))
PY
```

期望：

```text
OPENAI_API_KEY_SET= True
OPENAI_BASE_URL= https://api.openai.com/v1
OPENAI_FINE_TUNE_BASE_MODEL= 非空
OPENAI_FINE_TUNE_SUFFIX= zhiqi-sft
```

测试能否访问 OpenAI API：

```bash
docker compose exec -T app python - <<'PY'
import os
from openai import OpenAI

key = os.getenv("OPENAI_API_KEY", "")
if not key or key == "your-openai-api-key":
    raise SystemExit("FAIL: OPENAI_API_KEY missing")

client = OpenAI(
    api_key=key,
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)
models = client.models.list()
print("PASS: OpenAI API reachable, model_count=", len(models.data))
PY
```

意义：

- 只验证 Key 和网络连通性。
- 不创建训练任务。
- 不产生训练费用。

## 5. 真实授权样本准备

### 5.1 用户端怎么做

每个真实案例按这个流程完成：

```text
上传简历
-> 能力诊断
-> 简历润色
-> 加入学习任务
-> 至少 3 轮面试
-> 生成报告
-> 训练复盘
-> 在报告页或复盘页同意“本次案例加入去标识化评测库”
```

每一步意义：

- 上传简历：提供岗位和经历输入。
- 能力诊断：生成能力缺口和证据状态。
- 简历润色：验证简历证据口径是否能复用。
- 学习任务：证明诊断结果能转成训练行动。
- 至少 3 轮面试：形成追问上下文。
- 报告：沉淀优势、短板和建议。
- 训练复盘：记录用户训练反馈。
- 本次案例授权：允许该案例进入去标识化评测和训练准备。

### 5.2 后台怎么做

进入后台案例工作台或面试详情页，完成人工评分。

后台要确认：

```text
data_contribution_consent=true
review_status=reviewed
has_hallucination=false
至少有一个质量信号：is_high_quality / followup_worthy / report_actionable
```

意义：

- `data_contribution_consent=true`：用户授权。
- `review_status=reviewed`：人工复核完成。
- `has_hallucination=false`：不把幻觉反例混入正向 SFT。
- 质量信号：说明这条样本有训练价值。

注意：

- 未授权案例可以查看，但不能作为训练样本。
- AI 自动评分不能冒充人工评分。
- 构造样本不能冒充真实用户数据。

## 6. Dry-run 生成训练集

服务器执行：

```bash
cd /opt/apps/ai-interview
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset \
  --dry-run \
  --output-dir "$DATASET_DIR"
```

为什么显式写 `--output-dir`：

- Docker 容器里的默认路径不一定映射到宿主机。
- `/app/logs` 已经映射到服务器本机日志目录。
- 这样训练文件能在服务器上找得到。

宿主机对应目录通常是：

```text
/opt/apps/ai-interview/ai-interview-backend/logs/openai_fine_tuning_runs/latest/
```

这一步意义：

- 从数据库读取已授权、已人工复核的真实样本。
- 自动混入构造种子样本。
- 生成 OpenAI chat fine-tuning JSONL。
- 检查是否达到创建训练 job 的门槛。
- 不调用 OpenAI，不产生训练费用。

重点只看这几行：

```text
ready_for_openai_job=True
real_authorized_samples=3 或更多
constructed_samples=若干
train_samples=10 或更多
validation_samples=0 或更多
```

如果输出：

```text
ready_for_openai_job=False
blockers:
- 真实授权样本不足：当前 0 条，最低需要 3 条。
```

处理方式：

- 回用户端补真实案例。
- 确认用户勾选本次案例数据贡献授权。
- 后台完成人工评分。
- 再重新跑本步骤。

生成文件：

```text
train_openai.jsonl
validation_openai.jsonl
sample_manifest.jsonl
summary.json
README.md
```

文件意义：

- `train_openai.jsonl`：真正上传给 OpenAI 的训练集，只包含 `messages`。
- `validation_openai.jsonl`：验证集和 eval 使用。
- `sample_manifest.jsonl`：本地追溯样本来源，不作为 assistant 输出目标。
- `summary.json`：样本统计、阻塞项和是否可创建 job。
- `README.md`：本次训练数据说明。

## 7. 付费前预检

只有第 6 步输出：

```text
ready_for_openai_job=True
```

才执行：

```bash
cd /opt/apps/ai-interview
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job \
  --dry-run \
  --dataset-dir "$DATASET_DIR"
```

这一步意义：

- 检查训练集文件是否存在。
- 检查 `summary.json` 是否允许创建 job。
- 检查 base model 是否已配置。
- 不上传文件。
- 不创建 job。
- 不产生训练费用。

通过时会看到：

```text
PASS: create job preflight passed; dry_run=true, no OpenAI API call was made.
```

正式付费前人工确认清单：

```text
summary.json 里 ready_for_openai_job=true
real_authorized_samples >= 3
train_samples >= 10
OPENAI_API_KEY_SET=True
OPENAI_FINE_TUNE_BASE_MODEL 非空
确认愿意产生 OpenAI 训练费用
```

## 8. 创建 OpenAI 微调 job

确认第 7 步通过后执行：

```bash
cd /opt/apps/ai-interview
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job \
  --confirm-cost \
  --dataset-dir "$DATASET_DIR"
```

这一步意义：

- 上传 `train_openai.jsonl`。
- 如果有验证集，也上传 `validation_openai.jsonl`。
- 创建 OpenAI fine-tuning job。
- 这是付费操作，所以必须显式加 `--confirm-cost`。

成功后会生成：

```text
job_record.json
```

重点记录：

```text
fine_tuning_job.id
training_file_id
validation_file_id
base_model
```

重要提醒：

- 已生成 `job_record.json` 后，不要重复创建 job。
- 后续默认只查状态。
- 如果要重新训练，先明确这是新实验，再换新的输出目录。

常见报错：

| 报错 | 意义 | 处理 |
|---|---|---|
| `Dataset is not ready for OpenAI job` | 真实授权样本或训练样本不够 | 回到第 5 步补样本 |
| `OPENAI_FINE_TUNE_BASE_MODEL or --model is required` | 没填可微调 base model | 回到第 4 步配置 |
| `OPENAI_API_KEY is required` | Key 没配好或仍是占位值 | 回到第 4 步配置 |
| `model does not support fine-tuning` | base model 不支持微调 | 去 OpenAI 控制台换可 fine-tune 模型 |

## 9. 查询 job 状态

执行：

```bash
cd /opt/apps/ai-interview
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.check_openai_fine_tuning_job \
  --dataset-dir "$DATASET_DIR"
```

这一步意义：

- 查询 OpenAI job 当前状态。
- 保存状态到本地。
- 如果训练完成，会看到 `fine_tuned_model`。

输出重点：

```text
status=running / succeeded / failed
fine_tuned_model=ft:...
```

如果状态是 `running`：

- 每隔 5-10 分钟查一次。
- 不要重复创建新 job。

如果状态是 `failed`：

- 查看 `job_status.json`。
- 只修第一条真实失败原因。
- 不要改口径说训练成功。

如果 `job_record.json` 不在当前输出目录，但你手里有 OpenAI job id，可以显式指定：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.check_openai_fine_tuning_job \
  --dataset-dir "$DATASET_DIR" \
  --job-id <你的 OpenAI fine-tuning job id>
```

训练成功后，本地会有：

```text
job_status.json
```

并且里面应有：

```text
fine_tuned_model
```

## 10. Eval 对比

只有拿到 `fine_tuned_model` 后执行：

```bash
cd /opt/apps/ai-interview
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.run_fine_tuning_eval \
  --confirm-cost \
  --dataset-dir "$DATASET_DIR"
```

这一步意义：

- 用验证集对比 base model 和 fine-tuned model。
- 检查追问是否更贴近能力缺口。
- 检查是否减少编造候选人经历。
- 检查是否要求具体场景、行动、结果、指标。
- 检查 JSON 输出是否稳定。

成功后生成：

```text
eval_result.json
eval_result.md
```

如果报：

```text
Need at least 5 validation samples for eval
```

意义：

- 不是脚本坏了。
- 是验证集不够。
- 继续补真实样本，再重新生成训练集和验证集。

答辩材料摘录模板：

```text
OpenAI SFT job id：
Base model：
Fine-tuned model：
训练样本数：
真实授权样本数：
构造样本数：
验证样本数：
Eval 结论：
```

不要摘录：

- API Key。
- 未脱敏简历原文。
- 用户姓名、手机号、邮箱、学号、证件号、详细住址。

## 11. 答辩口径

未创建 job 前，只能说：

```text
已完成 OpenAI SFT 数据准备和启动脚本。
系统能够将授权、人工复核后的真实案例转换为 OpenAI chat fine-tuning JSONL。
```

创建 job 成功但没训练完时，可以说：

```text
已启动一次 OpenAI SFT 训练作业，当前处于训练或排队状态。
```

拿到 `fine_tuned_model` 后，可以说：

```text
已完成一次 OpenAI SFT 微调实验，并保存了 job id、模型 id 和样本统计。
```

跑完 eval 后，才可以说：

```text
我们用 holdout 样本对比了 base model 和 fine-tuned model，在追问聚焦、幻觉约束和格式稳定性上做了评估。
```

禁止说：

```text
我们自研了底层大模型。
我们已经完成大规模真实数据训练。
微调后效果提升 xx%。
构造样本来自真实用户。
不同意授权的用户数据也进入训练。
```

## 12. 常见卡点速查表

| 卡点 | 通常原因 | 处理 |
|---|---|---|
| `git pull` 后没有新脚本 | 本地没 push，或服务器分支不对 | 本地 `git push origin main`，服务器检查 `git branch` 和 `git log` |
| `No module named app.scripts.prepare_openai_fine_tuning_dataset` | 镜像没 rebuild 或代码没更新 | 重新 `git pull`，再 `docker compose up -d --build` |
| `ready_for_openai_job=False` | 真实授权样本或训练样本不足 | 看 `blockers`，补真实案例和后台评分 |
| `OPENAI_API_KEY required` | 容器没读到 `.env` 或 Key 是占位值 | 检查 `.env`，重建 app 容器 |
| `OPENAI_FINE_TUNE_BASE_MODEL required` | 没填 base model | 去 OpenAI 控制台确认可微调模型 |
| `model does not support fine-tuning` | base model 填错 | 换当前账号支持 fine-tuning 的模型 |
| `Need at least 5 validation samples` | 验证集不足 | 补样本，不要降低 eval 标准 |
| job 一直 `running` | 正常训练中或排队中 | 每 5-10 分钟查一次，不重复创建 |
| 找不到输出文件 | 没显式传 `--output-dir` 或看错目录 | 使用 `/app/logs/openai_fine_tuning_runs/latest` |

## 13. 最短命令清单

服务器更新：

```bash
cd /opt/apps/ai-interview
git pull
docker compose up -d --build
docker compose exec -T app alembic upgrade head
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset --help
```

配置检查：

```bash
docker compose exec -T app python - <<'PY'
import os
key = os.getenv("OPENAI_API_KEY", "")
print("OPENAI_API_KEY_SET=", bool(key and key != "your-openai-api-key"))
print("OPENAI_BASE_URL=", os.getenv("OPENAI_BASE_URL", ""))
print("OPENAI_FINE_TUNE_BASE_MODEL=", os.getenv("OPENAI_FINE_TUNE_BASE_MODEL", ""))
print("OPENAI_FINE_TUNE_SUFFIX=", os.getenv("OPENAI_FINE_TUNE_SUFFIX", ""))
PY
```

生成训练集：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset \
  --dry-run \
  --output-dir "$DATASET_DIR"
```

付费前预检：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job \
  --dry-run \
  --dataset-dir "$DATASET_DIR"
```

创建真实 job：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job \
  --confirm-cost \
  --dataset-dir "$DATASET_DIR"
```

查询状态：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.check_openai_fine_tuning_job \
  --dataset-dir "$DATASET_DIR"
```

评估对比：

```bash
DATASET_DIR=/app/logs/openai_fine_tuning_runs/latest
docker compose exec -T app python -m app.scripts.run_fine_tuning_eval \
  --confirm-cost \
  --dataset-dir "$DATASET_DIR"
```

## 14. 完成判断

| 阶段 | 判断标准 | 是否可以写入答辩 |
|---|---|---|
| 只生成训练集 | `summary.json` 存在，且可看到样本统计 | 只能说完成 SFT 数据准备 |
| 付费前预检 | `job_preflight.json` 存在 | 可以说创建前检查通过 |
| 创建 job | `job_record.json` 存在，且有 job id | 可以说已启动 OpenAI SFT 作业 |
| 训练成功 | `job_status.json` 中有 `fine_tuned_model` | 可以说完成一次 OpenAI SFT 实验 |
| 对比评估 | `eval_result.md` 存在 | 可以说完成 base/fine-tuned 对照评估 |

## 15. 输出文件不要提交

训练输出目录：

```text
/opt/apps/ai-interview/ai-interview-backend/logs/openai_fine_tuning_runs/
```

不要提交它，原因：

- 里面可能包含真实样本统计和训练记录。
- 不应把真实训练输出和隐私相关追溯信息直接提交到仓库。
- 如果需要答辩材料，只摘录必要摘要，不复制原始样本。
