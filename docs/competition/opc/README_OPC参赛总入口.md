# 职启智评 OPC 参赛总入口

## 1. 项目新定位

参赛主张：

```text
职启智评 OPC：一个人 + AI Agents 的高校就业能力诊断与训练服务单元
```

本次不是把项目简单包装成“AI 面试平台”，而是把现有可运行系统解释为一个 OPC 超级个体的 AI 原生工作流：一个人负责目标、边界、验收和最终责任；ChatGPT、Codex、业务大模型、Eval/后台评分共同承担调研、工程、业务生成、评估和材料生产。

## 2. 赛事适配依据

- 国科大现代产业学院关于“京彩AI·智汇全球”北京大学生“超级个体”（OPC）创业大赛通知：`https://sie.ucas.ac.cn/index.php?a=index&cid=27&g=&id=1433&m=article`
- 北京市教育委员会第五届“京彩大创”北京大学生创新创业大赛总通知：`https://jw.beijing.gov.cn/tzgg/202603/t20260318_4004613.html`

赛事口径强调 AI 原生结构、人机协同逻辑、产业场景嵌入、轻量化创新单元和集中限时实测。职启智评对应的垂直场景是高校就业服务和大学生求职能力训练。

## 3. 阅读顺序

```text
01_赛事适配判断.md
02_OPC参赛主叙事.md
03_AI工作流总图.md
04_人机协同分工图.md
06_答辩PPT_OPC版页面结构.md
07_三分钟讲稿_OPC版.md
08_八分钟讲稿_OPC版.md
09_评委问答库_OPC版.md
10_一人OPC日常运行手册.md
11_三个月补实路线.md
12_可展示成果与不能夸大边界.md
live_test_drills/
```

## 4. 当前真实状态

已具备：

- Vue 用户端、Vue 后台、FastAPI 后端、PostgreSQL、Redis/Celery、Docker Compose。
- 简历解析、岗位画像、证据评分、能力差距、简历润色、学习任务、模拟面试、报告、训练复盘、后台评分。
- Career-AgentOS Preview：三岗位 demo、Agent Trace、Eval Preview、SFT Preview。
- 数据治理门禁：基础隐私协议、可选数据贡献授权、去标识化、人工复核、PII 扫描、SFT-ready 准入。

当前不能夸大：

- C1/C2/C3 真实闭环尚未全部完成。
- 真实 OpenAI SFT 尚未启动，尚无官方微调模型 ID。
- demo_constructed 样本不是用户真实数据，Eval Preview 不是真实 holdout eval。
