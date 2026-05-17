#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/apps/ai-interview}"
API_LOCAL_PORT="${API_LOCAL_PORT:-18001}"
REPORT_PATH="${REPORT_PATH:-docs/competition/server_validation_reports/stage138_server_closed_loop_latest.md}"

DO_DEPLOY=0
ALLOW_DESTRUCTIVE_RESET="${ALLOW_DESTRUCTIVE_RESET:-0}"
READINESS_ONLY=0
REPORT_ENABLED=1
REPORT_WRITTEN=0
STARTED_AT="$(date -Iseconds 2>/dev/null || date)"
PROJECT_COMMIT_BEFORE=""
PROJECT_COMMIT_AFTER=""
capacity_output=""
core_output=""
closed_loop_output=""
admin_root_output=""
recent_errors=""
CHECK_NAMES=()
CHECK_RESULTS=()
CHECK_NOTES=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/stage138_server_closed_loop_verify.sh [--deploy] [--allow-reset] [--readiness-only] [--report PATH] [--no-report]

Stage 138 verifies deployment readiness plus the C1/C2/C3 closed-loop data gate.

Default mode:
  - checks container health
  - runs alembic upgrade head
  - runs database capacity self-check
  - runs stage 133 core self-check
  - checks root admin permission state
  - validates R1/R2/R3 closed-loop CSV records
  - writes a Markdown report

Use --readiness-only before manual C1/C2/C3 run tests. In that mode incomplete
closed-loop records are recorded as WARN instead of failing the whole script.

Environment overrides:
  PROJECT_DIR=/opt/apps/ai-interview
  API_LOCAL_PORT=18001
  ALLOW_DESTRUCTIVE_RESET=1
  REPORT_PATH=docs/competition/server_validation_reports/stage138_server_closed_loop_latest.md

Safety:
  --deploy fetches origin/main but refuses git reset --hard unless --allow-reset
  or ALLOW_DESTRUCTIVE_RESET=1 is provided.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --deploy)
      DO_DEPLOY=1
      ;;
    --allow-reset)
      ALLOW_DESTRUCTIVE_RESET=1
      ;;
    --readiness-only)
      READINESS_ONLY=1
      ;;
    --report)
      if [ "$#" -lt 2 ]; then
        echo "--report requires a path" >&2
        exit 2
      fi
      REPORT_PATH="$2"
      shift
      ;;
    --no-report)
      REPORT_ENABLED=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
  shift
done

section() {
  printf '\n== %s ==\n' "$1"
}

run() {
  echo "+ $*"
  "$@"
}

failures=0
warnings=0

record_check() {
  CHECK_NAMES+=("$1")
  CHECK_RESULTS+=("$2")
  CHECK_NOTES+=("$3")
}

soft_check() {
  local name="$1"
  shift
  echo "+ $*"
  if "$@"; then
    echo "PASS: $name"
    record_check "$name" "PASS" "$*"
  else
    echo "FAIL: $name" >&2
    failures=$((failures + 1))
    record_check "$name" "FAIL" "$*"
  fi
}

warn_check() {
  local name="$1"
  local note="$2"
  echo "WARN: $name - $note"
  warnings=$((warnings + 1))
  record_check "$name" "WARN" "$note"
}

python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    return 127
  fi
}

write_report() {
  if [ "$REPORT_ENABLED" -ne 1 ] || [ "$REPORT_WRITTEN" -eq 1 ]; then
    return
  fi

  local overall_status="${1:-UNKNOWN}"
  local finished_at
  finished_at="$(date -Iseconds 2>/dev/null || date)"
  mkdir -p "$(dirname "$REPORT_PATH")"

  {
    echo "# 阶段 138 服务器真实闭环验收报告"
    echo
    echo "| 项目 | 结果 |"
    echo "|---|---|"
    echo "| 开始时间 | ${STARTED_AT} |"
    echo "| 结束时间 | ${finished_at} |"
    echo "| 项目目录 | \`${PROJECT_DIR}\` |"
    echo "| 部署模式 | $([ "$DO_DEPLOY" -eq 1 ] && echo "deploy" || echo "verify-only") |"
    echo "| Readiness only | $([ "$READINESS_ONLY" -eq 1 ] && echo "yes" || echo "no") |"
    echo "| 执行前提交 | ${PROJECT_COMMIT_BEFORE:-未记录} |"
    echo "| 执行后提交 | ${PROJECT_COMMIT_AFTER:-未记录} |"
    echo "| 自动结论 | ${overall_status} |"
    echo
    echo "## 自动检查结果"
    echo
    echo "| 检查项 | 结果 | 命令或说明 |"
    echo "|---|---|---|"
    local idx
    for idx in "${!CHECK_NAMES[@]}"; do
      echo "| ${CHECK_NAMES[$idx]} | ${CHECK_RESULTS[$idx]} | \`${CHECK_NOTES[$idx]}\` |"
    done
    if [ "${#CHECK_NAMES[@]}" -eq 0 ]; then
      echo "| 暂无 | UNKNOWN | 脚本在执行早期中断，查看终端输出定位第一条异常 |"
    fi
    echo
    echo "## PostgreSQL 容量自检"
    echo
    if [ -n "${capacity_output:-}" ]; then
      echo '```text'
      printf '%s\n' "$capacity_output"
      echo '```'
    else
      echo "未执行或未捕获容量自检输出。"
    fi
    echo
    echo "## 阶段 133 核心自检"
    echo
    if [ -n "${core_output:-}" ]; then
      echo '```text'
      printf '%s\n' "$core_output"
      echo '```'
    else
      echo "未执行或未捕获阶段 133 自检输出。"
    fi
    echo
    echo "## 阶段 138 三岗位闭环 CSV 检查"
    echo
    if [ -n "${closed_loop_output:-}" ]; then
      echo '```text'
      printf '%s\n' "$closed_loop_output"
      echo '```'
    else
      echo "未执行或未捕获三岗位闭环检查输出。"
    fi
    echo
    echo "## Root 管理员检查"
    echo
    if [ -n "${admin_root_output:-}" ]; then
      echo '```text'
      printf '%s\n' "$admin_root_output"
      echo '```'
    else
      echo "未执行或未捕获 root 管理员 SQL 输出。"
    fi
    echo
    echo "## 最近后端关键日志"
    echo
    if [ -n "${recent_errors:-}" ]; then
      echo '```text'
      printf '%s\n' "$recent_errors"
      echo '```'
    else
      echo "未在最近 300 行 app 日志中检出关键错误。"
    fi
    echo
    echo "## 人工验收必须补齐"
    echo
    echo "- 阶段 135：root 管理员、普通管理员、授权管理员、改密、删除保护。"
    echo "- 阶段 136：上传真实 PDF，确认 parse_quality、normalized_resume 和开始面试不闪退。"
    echo "- 阶段 132/138：C1/C2/C3 均完成诊断、润色、学习任务、至少 3 轮面试、报告、训练复盘和后台人工评分。"
    echo "- 如果自动结论为 FAIL：只处理第一条失败原因，不新增功能绕开真实验收。"
  } > "$REPORT_PATH"

  REPORT_WRITTEN=1
  echo "Report written: $REPORT_PATH"
}

on_exit() {
  local code=$?
  if [ "$code" -ne 0 ] && [ "$REPORT_WRITTEN" -eq 0 ]; then
    write_report "FAIL_EARLY"
  fi
}

trap on_exit EXIT

check_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 127
  fi
}

check_command git
check_command docker
check_command curl
check_command grep
PYTHON_BIN="$(python_cmd)" || {
  echo "Missing required command: python3 or python" >&2
  exit 127
}

section "Project"
cd "$PROJECT_DIR"
pwd
git rev-parse --is-inside-work-tree >/dev/null
echo "branch: $(git branch --show-current)"
PROJECT_COMMIT_BEFORE="$(git log --oneline -1)"
PROJECT_COMMIT_AFTER="$PROJECT_COMMIT_BEFORE"
echo "commit: $PROJECT_COMMIT_BEFORE"

if [ "$DO_DEPLOY" -eq 1 ]; then
  section "Deploy origin/main"
  run git fetch origin
  if [ "$ALLOW_DESTRUCTIVE_RESET" != "1" ]; then
    echo "Refusing to run git reset --hard origin/main without explicit approval." >&2
    echo "Re-run with --allow-reset or ALLOW_DESTRUCTIVE_RESET=1 after confirming no local server changes must be kept." >&2
    exit 2
  fi
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "WARNING: local uncommitted changes will be discarded by git reset --hard origin/main." >&2
  fi
  run git reset --hard origin/main
  PROJECT_COMMIT_AFTER="$(git log --oneline -1)"
  echo "after reset: $PROJECT_COMMIT_AFTER"

  section "Build stage 138 services"
  run docker compose up -d --build app admin frontend
fi

section "Docker status"
run docker compose ps

section "Database migration"
soft_check "alembic upgrade head" docker compose exec -T app alembic upgrade head

section "HTTP health"
soft_check "backend health" curl -fsS "http://127.0.0.1:${API_LOCAL_PORT}/api/v1/config/health"

section "PostgreSQL capacity"
if capacity_output="$(docker compose exec -T app python -m app.scripts.check_database_capacity 2>&1)"; then
  echo "$capacity_output"
  record_check "database capacity self-check" "PASS" "python -m app.scripts.check_database_capacity"
else
  echo "$capacity_output"
  failures=$((failures + 1))
  record_check "database capacity self-check" "FAIL" "python -m app.scripts.check_database_capacity"
fi

section "Stage 133 core self-check"
if core_output="$(docker compose exec -T app python -m app.scripts.check_core_feature_flow --print-only 2>&1)"; then
  echo "$core_output" | tail -n 40
  record_check "stage 133 core self-check" "PASS" "python -m app.scripts.check_core_feature_flow --print-only"
else
  echo "$core_output"
  failures=$((failures + 1))
  record_check "stage 133 core self-check" "FAIL" "python -m app.scripts.check_core_feature_flow --print-only"
fi

section "Root admin permission"
admin_root_output="$(
  docker compose exec -T postgres sh -lc \
    "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"select email || '|' || can_manage_admins::text from admins where email='autsky6666@gmail.com';\"" \
    2>&1 || true
)"
echo "$admin_root_output"
if printf '%s' "$admin_root_output" | grep -q "autsky6666@gmail.com|true"; then
  record_check "root admin can_manage_admins" "PASS" "autsky6666@gmail.com has can_manage_admins=true"
else
  failures=$((failures + 1))
  record_check "root admin can_manage_admins" "FAIL" "root admin missing or can_manage_admins is not true"
fi

section "Stage 138 C1/C2/C3 closed-loop CSV"
if closed_loop_output="$("$PYTHON_BIN" scripts/validate_stage138_closed_loop.py 2>&1)"; then
  echo "$closed_loop_output"
  record_check "stage 138 closed-loop CSV" "PASS" "python scripts/validate_stage138_closed_loop.py"
else
  echo "$closed_loop_output"
  if [ "$READINESS_ONLY" -eq 1 ]; then
    warn_check "stage 138 closed-loop CSV" "C1/C2/C3 records are not complete yet; readiness-only mode keeps this as WARN"
  else
    failures=$((failures + 1))
    record_check "stage 138 closed-loop CSV" "FAIL" "python scripts/validate_stage138_closed_loop.py"
  fi
fi

section "Recent app errors"
recent_errors="$(docker compose logs --tail=300 app | grep -Ei "Traceback|UndefinedColumn|relation .* does not exist|interviews/start|learning-tasks|learning-plans|resume.*polish|position_knowledge|too many connections|TimeoutError|asyncpg" || true)"
if [ -n "$recent_errors" ]; then
  printf '%s\n' "$recent_errors"
  record_check "recent app error scan" "WARN" "recent app logs contain matched keywords"
  warnings=$((warnings + 1))
else
  echo "PASS: no recent key app errors matched"
  record_check "recent app error scan" "PASS" "no matched key errors"
fi

section "Summary"
if [ "$failures" -eq 0 ]; then
  if [ "$warnings" -gt 0 ]; then
    echo "WARN: server readiness passed with ${warnings} warning(s)."
    write_report "WARN"
    exit 0
  fi
  echo "PASS: stage 138 server checks passed."
  write_report "PASS"
  exit 0
fi

echo "FAIL: ${failures} validation check(s) failed." >&2
echo "Next step: fix the first failing command or first closed-loop record gap." >&2
write_report "FAIL"
exit 1
