# 职启智评 OpenAI SFT 真实微调操作手册

更新时间：2026-05-16  
适用项目：`D:\apps\ai-interview`  
服务器目录：`/opt/apps/ai-interview`  
适用阶段：阶段 144：OpenAI SFT 真实微调启动

## 0. 先看结论

当前项目已经具备 OpenAI SFT 启动脚本，但还没有完成真实微调。

你现在要按顺序完成：

1. 服务器更新到最新代码。
2. 配置官方 OpenAI Key 和可微调模型。
3. 跑出至少 3 条“已授权 + 已人工复核”的真实案例。
4. 生成 OpenAI 训练集。
5. 创建 OpenAI fine-tuning job。
6. 查询训练状态。
7. 拿到 `fine_tuned_model` 后做 base model 对比评估。

只有拿到 `fine_tuned_model` 后，答辩里才能说：

```text
已完成一次 OpenAI SFT 微调实验。
```

## 1. 服务器更新代码

执行：

```bash
cd /opt/apps/ai-interview
git pull
docker compose up -d --build
docker compose exec -T app alembic upgrade head
```

每一步意义：

- `git pull`：拉取阶段 144 的 OpenAI SFT 脚本。
- `docker compose up -d --build`：重新构建镜像，让新增脚本进入 app 容器。
- `alembic upgrade head`：确认数据库结构是最新状态。

检查：

```bash
docker compose ps
curl -fsS http://127.0.0.1:18001/api/v1/config/health
```

期望：

- `app`、`postgres`、`redis` 是 healthy。
- health 接口返回 database 和 redis 都是 up。

## 2. 配置 OpenAI 官方 Key

编辑服务器 `.env`：

```bash
nano .env
```

补齐或确认：

```env
OPENAI_API_KEY=sk-你的官方OpenAIKey
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_FINE_TUNE_BASE_MODEL=你当前账号支持的可微调模型ID
OPENAI_FINE_TUNE_SUFFIX=zhiqi-sft
```

每一项意义：

- `OPENAI_API_KEY`：官方 OpenAI Key，用于上传训练文件、创建微调 job、查询状态和跑 eval。
- `OPENAI_BASE_URL`：正式微调使用官方地址。
- `OPENAI_FINE_TUNE_BASE_MODEL`：OpenAI 当前支持 fine-tuning 的 base model。
- `OPENAI_FINE_TUNE_SUFFIX`：训练后模型名后缀，方便识别为职启智评实验。

改完重启：

```bash
docker compose up -d
```

注意：

- 不要把 API Key 写进仓库。
- 不要截图泄露 API Key。
- 不要用来源不明的中转 Key 做正式训练。
- 不确定模型 ID 时，先去 OpenAI 控制台或官方 fine-tuning 文档确认。

## 3. 准备真实授权样本

最低门槛：

- 真实授权样本不少于 3 条。
- 总训练样本不少于 10 条。
- 构造样本可以补数量，但不能替代真实样本。

每个真实案例必须完成：

```text
上传简历
-> 能力诊断
-> 简历润色
-> 加入学习任务
-> 至少 3 轮面试
-> 生成报告
-> 训练复盘
-> 用户同意“本次案例加入去标识化评测库”
-> 后台人工评分
```

每一步意义：

- 上传简历：提供候选人的岗位和经历输入。
- 能力诊断：生成能力缺口和证据状态。
- 简历润色：验证简历证据口径是否能复用。
- 学习任务：证明诊断结果能转成训练行动。
- 至少 3 轮面试：保证样本不是空壳，能形成追问上下文。
- 报告：沉淀优势、短板和建议。
- 训练复盘：记录用户训练反馈。
- 本次案例授权：解决真实样本进入训练/评测前的合规前提。
- 后台人工评分：解决训练样本质量前提。

后台人工评分时重点确认：

```text
review_status=reviewed
data_contribution_consent=true
has_hallucination=false
至少有一个质量信号：is_high_quality / followup_worthy / report_actionable
```

如果没有真实授权样本，不要继续创建 OpenAI job。

## 4. 生成 OpenAI 训练集

推荐直接在宿主机执行：

```bash
cd /opt/apps/ai-interview
docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset --dry-run
```

也可以进入容器后执行：

```bash
docker compose exec -T app bash
python -m app.scripts.prepare_openai_fine_tuning_dataset --dry-run
```

这一步意义：

- 从数据库读取“已授权 + 已人工复核”的真实样本。
- 自动混入构造种子样本。
- 生成 OpenAI chat fine-tuning JSONL。
- 检查是否达到创建训练 job 的门槛。
- 不调用 OpenAI，不花钱。

重点看输出：

```text
ready_for_openai_job=True
real_authorized_samples=3 或更多
constructed_samples=若干
train_samples=10 或更多
```

如果输出：

```text
ready_for_openai_job=False
真实授权样本不足
```

处理方式：

- 回系统补真实案例。
- 确认用户勾选本次案例数据贡献授权。
- 后台完成人工评分。
- 不要强行降低门槛包装成果。

生成文件位置：

```text
docs/competition/openai_fine_tuning_runs/latest/
```

主要文件：

```text
train_openai.jsonl
validation_openai.jsonl
sample_manifest.jsonl
summary.json
README.md
```

文件意义：

- `train_openai.jsonl`：真正上传给 OpenAI 的训练集，只包含 `messages`。
- `validation_openai.jsonl`：验证集和后续 eval 使用。
- `sample_manifest.jsonl`：本地追溯样本来源，不作为 assistant 输出目标。
- `summary.json`：样本统计、阻塞项和是否可创建 job。
- `README.md`：本次训练数据说明。

## 5. 创建 OpenAI 微调任务

只有第 4 步显示：

```text
ready_for_openai_job=True
```

才执行：

```bash
cd /opt/apps/ai-interview
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job --confirm-cost
```

这一步意义：

- 上传 `train_openai.jsonl`。
- 如果有验证集，也上传 `validation_openai.jsonl`。
- 创建 OpenAI fine-tuning job。
- 这是付费操作，所以必须显式加 `--confirm-cost`。

成功后会生成：

```text
docs/competition/openai_fine_tuning_runs/latest/job_record.json
```

重点记录：

```text
fine_tuning_job.id
training_file_id
validation_file_id
base_model
```

常见报错和处理：

| 报错 | 意义 | 处理 |
|---|---|---|
| `Dataset is not ready for OpenAI job` | 真实授权样本或训练样本不够 | 回到第 3 步补样本 |
| `OPENAI_FINE_TUNE_BASE_MODEL or --model is required` | 没填可微调 base model | 回到第 2 步配置 |
| `OPENAI_API_KEY is required` | Key 没配好或仍是占位值 | 回到第 2 步配置 |
| OpenAI 返回模型不支持微调 | base model 不在账号支持范围 | 去官方控制台确认可用模型 |

## 6. 查询训练状态

执行：

```bash
cd /opt/apps/ai-interview
docker compose exec -T app python -m app.scripts.check_openai_fine_tuning_job
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

- 等一段时间后再查。
- 不要重复创建新 job。

如果状态是 `failed`：

- 查看 `docs/competition/openai_fine_tuning_runs/latest/job_status.json`。
- 先修第一条失败原因。
- 不要改口径说已经训练成功。

训练成功后，本地会有：

```text
docs/competition/openai_fine_tuning_runs/latest/job_status.json
```

## 7. 做微调前后对比评估

只有拿到 `fine_tuned_model` 后执行：

```bash
cd /opt/apps/ai-interview
docker compose exec -T app python -m app.scripts.run_fine_tuning_eval --confirm-cost
```

这一步意义：

- 用验证集对比 base model 和 fine-tuned model。
- 检查追问是否更贴近能力缺口。
- 检查是否减少编造候选人经历。
- 检查是否要求具体场景、行动、结果、指标。
- 检查 JSON 输出是否稳定。

成功后生成：

```text
docs/competition/openai_fine_tuning_runs/latest/eval_result.json
docs/competition/openai_fine_tuning_runs/latest/eval_result.md
```

答辩时可以用：

- `job_record.json`：证明创建了真实 job。
- `job_status.json`：证明拿到了模型 ID。
- `eval_result.md`：证明做了对照评估。

注意：

- 如果验证集少于 5 条，eval 会拒绝执行。
- 这时继续补真实样本，不要降低评估标准。

## 8. 答辩表述口径

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

## 9. 最短执行清单

服务器上按这个顺序跑：

```bash
cd /opt/apps/ai-interview

git pull
docker compose up -d --build
docker compose exec -T app alembic upgrade head

docker compose exec -T app python -m app.scripts.prepare_openai_fine_tuning_dataset --dry-run
```

如果 `ready_for_openai_job=False`：

```text
回系统补真实授权案例和后台人工评分。
```

如果 `ready_for_openai_job=True`：

```bash
docker compose exec -T app python -m app.scripts.create_openai_fine_tuning_job --confirm-cost
docker compose exec -T app python -m app.scripts.check_openai_fine_tuning_job
```

训练成功后：

```bash
docker compose exec -T app python -m app.scripts.run_fine_tuning_eval --confirm-cost
```

## 10. 输出文件不要提交

以下目录是训练运行输出，默认不提交 Git：

```text
docs/competition/openai_fine_tuning_runs/
```

原因：

- 里面可能包含真实样本统计和训练记录。
- 不应把真实训练输出和隐私相关追溯信息直接提交到仓库。
- 当前 `.gitignore` 已排除该目录。

如果后续要放进答辩材料，只复制必要摘要：

- job id。
- base model。
- fine-tuned model id。
- 样本数量。
- eval 摘要。

不要复制：

- API Key。
- 未脱敏简历原文。
- 用户姓名、手机号、邮箱、学号、证件号、详细住址。

## 11. 当前默认假设

- 继续使用服务器路径 `/opt/apps/ai-interview`。
- 使用官方 OpenAI API，不用中转 Key 做正式训练。
- 第一版只做 OpenAI SFT，不做 DPO、RFT、LoRA 或本地模型训练。
- 构造样本只做补充，不冒充真实数据。
- C1/C2/C3 真实闭环仍然后移，但至少要补 3 条真实授权样本才能启动正式微调。
- `docs/competition/openai_fine_tuning_runs/` 是训练输出目录，默认不提交到 Git。

## 12. 完成判断

| 阶段 | 判断标准 | 是否可以写入答辩 |
|---|---|---|
| 只生成训练集 | `summary.json` 存在，且可看到样本统计 | 只能说完成 SFT 数据准备 |
| 创建 job | `job_record.json` 存在，且有 job id | 可以说已启动 OpenAI SFT 作业 |
| 训练成功 | `job_status.json` 中有 `fine_tuned_model` | 可以说完成一次 OpenAI SFT 实验 |
| 对比评估 | `eval_result.md` 存在 | 可以说完成 base/fine-tuned 对照评估 |
