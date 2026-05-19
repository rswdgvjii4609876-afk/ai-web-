#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/apps/ai-interview}"
API_LOCAL_PORT="${API_LOCAL_PORT:-18001}"
FRONTEND_LOCAL_PORT="${FRONTEND_LOCAL_PORT:-13000}"
ADMIN_LOCAL_PORT="${ADMIN_LOCAL_PORT:-13001}"
MIN_PUBLIC_PROFILES="${MIN_PUBLIC_PROFILES:-12}"
REPORT_PATH="${REPORT_PATH:-docs/competition/server_validation_reports/stage79_server_verify_latest.md}"

DO_DEPLOY=0
SKIP_SEED=0
REPORT_ENABLED=1
REPORT_WRITTEN=0
STARTED_AT="$(date -Iseconds 2>/dev/null || date)"
PROJECT_COMMIT_BEFORE=""
PROJECT_COMMIT_AFTER=""
public_count=""
slice_count=""
recent_errors=""
CHECK_NAMES=()
CHECK_RESULTS=()
CHECK_NOTES=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/stage79_server_verify.sh [--deploy] [--skip-seed] [--report PATH] [--no-report]

Default mode only verifies the running server.
Use --deploy to fetch origin/main, reset server code, rebuild services, run migrations and seed public profiles.
By default the script writes a Markdown report to docs/competition/server_validation_reports/stage79_server_verify_latest.md.

Environment overrides:
  PROJECT_DIR=/opt/apps/ai-interview
  API_LOCAL_PORT=18001
  FRONTEND_LOCAL_PORT=13000
  ADMIN_LOCAL_PORT=13001
  MIN_PUBLIC_PROFILES=12
  REPORT_PATH=docs/competition/server_validation_reports/stage79_server_verify_latest.md
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --deploy)
      DO_DEPLOY=1
      ;;
    --skip-seed)
      SKIP_SEED=1
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

write_report() {
  if [ "$REPORT_ENABLED" -ne 1 ] || [ "$REPORT_WRITTEN" -eq 1 ]; then
    return
  fi

  local overall_status="${1:-UNKNOWN}"
  local finished_at
  finished_at="$(date -Iseconds 2>/dev/null || date)"
  mkdir -p "$(dirname "$REPORT_PATH")"

  {
    echo "# 职启智评服务器阶段 79 验收报告"
    echo
    echo "| 项目 | 结果 |"
    echo "|---|---|"
    echo "| 开始时间 | ${STARTED_AT} |"
    echo "| 结束时间 | ${finished_at} |"
    echo "| 项目目录 | \`${PROJECT_DIR}\` |"
    echo "| 部署模式 | $([ "$DO_DEPLOY" -eq 1 ] && echo "deploy" || echo "verify-only") |"
    echo "| 跳过种子 | $([ "$SKIP_SEED" -eq 1 ] && echo "yes" || echo "no") |"
    echo "| 执行前提交 | ${PROJECT_COMMIT_BEFORE:-未记录} |"
    echo "| 执行后提交 | ${PROJECT_COMMIT_AFTER:-未记录} |"
    echo "| 公共岗位画像 | ${public_count:-未读取} |"
    echo "| 知识切片 | ${slice_count:-未读取} |"
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
    echo "## 人工验收入口"
    echo
    echo "- 用户端：上传真实简历 -> 能力诊断 -> 加入学习任务 -> 开始模拟面试 -> 报告 -> 训练复盘。"
    echo "- 后台端：公共岗位画像不少于 ${MIN_PUBLIC_PROFILES} 个，切片数大于 0，测评样本页无红色 500。"
    echo "- 若自动结论为 FAIL：优先处理终端或本报告中的第一条失败项。"
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
  run git pull --ff-only origin main
  PROJECT_COMMIT_AFTER="$(git log --oneline -1)"
  echo "after fast-forward pull: $PROJECT_COMMIT_AFTER"

  section "Build services"
  run docker compose up -d --build app frontend admin

  section "Database migration"
  run docker compose exec -T app alembic upgrade head

  if [ "$SKIP_SEED" -eq 0 ]; then
    section "Seed public position profiles"
    run docker compose exec -T app python -m app.scripts.seed_competition_knowledge_bases
  fi

  section "Restart services"
  run docker compose restart app frontend admin
fi

section "Docker status"
run docker compose ps

section "Environment check"
if [ -f .env ]; then
  grep -E '^(REDIS_HOST|REDIS_PORT)=' .env || true
  grep -E '^(REDIS_PASSWORD|CELERY_BROKER_URL|CELERY_RESULT_BACKEND)=' .env | sed -E 's/=.*/=<redacted>/' || true
  redis_port="$(grep -E '^REDIS_PORT=' .env | tail -n 1 | cut -d= -f2- | tr -d '"'\''[:space:]' || true)"
  if [ -n "$redis_port" ] && ! printf '%s' "$redis_port" | grep -Eq '^[0-9]+$'; then
    echo "FAIL: REDIS_PORT is not numeric: $redis_port" >&2
    failures=$((failures + 1))
    record_check "REDIS_PORT numeric" "FAIL" "REDIS_PORT=$redis_port"
  elif [ -n "$redis_port" ]; then
    record_check "REDIS_PORT numeric" "PASS" "REDIS_PORT=$redis_port"
  fi
else
  echo "WARN: .env not found"
  record_check ".env file" "WARN" ".env not found"
fi

section "HTTP health"
soft_check "backend health" curl -fsS "http://127.0.0.1:${API_LOCAL_PORT}/api/v1/config/health"
soft_check "frontend shell" curl -fsS "http://127.0.0.1:${FRONTEND_LOCAL_PORT}/"
soft_check "admin shell" curl -fsS "http://127.0.0.1:${ADMIN_LOCAL_PORT}/"

section "Database profile counts"
public_count="$(
  docker compose exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from position_knowledge_bases where scope='"'"'public'"'"';"' \
    | tr -dc '0-9'
)"
slice_count="$(
  docker compose exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from position_knowledge_base_slices;"' \
    | tr -dc '0-9'
)"
echo "public_profiles=${public_count:-0}"
echo "knowledge_slices=${slice_count:-0}"

if [ "${public_count:-0}" -lt "$MIN_PUBLIC_PROFILES" ]; then
  echo "FAIL: public profiles less than ${MIN_PUBLIC_PROFILES}" >&2
  failures=$((failures + 1))
  record_check "public profile count" "FAIL" "public_profiles=${public_count:-0}, required=${MIN_PUBLIC_PROFILES}"
else
  record_check "public profile count" "PASS" "public_profiles=${public_count:-0}"
fi

if [ "${slice_count:-0}" -le 0 ]; then
  echo "FAIL: knowledge slices are empty" >&2
  failures=$((failures + 1))
  record_check "knowledge slice count" "FAIL" "knowledge_slices=${slice_count:-0}"
else
  record_check "knowledge slice count" "PASS" "knowledge_slices=${slice_count:-0}"
fi

section "Recent app errors"
recent_errors="$(docker compose logs --tail=300 app | grep -Ei "Traceback|UndefinedColumn|relation .* does not exist|interviews/start|evaluation-datasets|celery|redis" || true)"
if [ -n "$recent_errors" ]; then
  printf '%s\n' "$recent_errors"
  record_check "recent app error scan" "WARN" "recent app logs contain matched keywords"
else
  echo "PASS: no recent key app errors matched"
  record_check "recent app error scan" "PASS" "no matched key errors"
fi

section "Summary"
if [ "$failures" -eq 0 ]; then
  echo "PASS: server validation checks passed."
  write_report "PASS"
  exit 0
fi

echo "FAIL: ${failures} validation check(s) failed." >&2
echo "Next step: copy the first backend traceback or failing command output into the task record." >&2
write_report "FAIL"
exit 1
