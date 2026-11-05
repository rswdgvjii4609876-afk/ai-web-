# 2026-11-05：反馈接口隐私同意检查

实施方式：本次由 Codex 辅助检查、修改和测试。以下仅记录本次实际操作；原作者既有功能和历史提交保持原归属。本项属于接手后的工程维护贡献。

## 问题与复现

上游基线 `3200645a046a515488b8b19d8d0fc19155dddede` 的完整后端测试为 285 项通过、1 项失败。失败项是 `tests/test_privacy_stage152_exposure.py::test_client_routes_do_not_bypass_base_privacy_gate`。

三个客户端反馈接口直接检查登录，未复用项目的基础隐私同意依赖。先扩展现有 HTTP 测试，检查用户缺少同意和仅有旧版同意两种情况。测试在业务代码修改前实际失败：接口返回 200，预期为 400。

## 实际修改

- `app/api/client/v1/feedback.py`：创建、列表和详情接口均使用 `require_base_privacy_consent`，复用已有登录与当前版本隐私同意校验。
- `tests/test_feedback.py`：通过 HTTP 请求验证缺失、旧版同意会被拒绝，并以已同意用户继续验证创建、列表、用户隔离、后台回复及参数校验。
- 更新 README 和可行性报告中的当前测试状态。

## 验证

在 `ai-interview-backend/` 内，使用工作区 Python 3.12.14 虚拟环境：

```sh
python -m pytest -q --tb=short tests/test_feedback.py::test_feedback_http_auth_validation_and_reply_flow
python -m pytest -q --tb=short --junitxml=../../backend-tests-after-fix.xml
```

第一条命令在修复前用于确认新覆盖能复现问题；第二条在修复后运行，结果为 **286 passed in 3.43s**。

测试模型密钥使用占位值，没有付费模型调用。HTTP 测试使用内存 SQLite 和测试身份替身；本次没有验收真实数据库、Redis、模型接口或完整浏览器流程。

## 当前边界

本次没有重写项目、调整原作者提交日期或补造历史开发过程。没有进行云端部署。独立设计的新产品功能、真实模型效果验证和赛事原创性确认仍需分别完成。
