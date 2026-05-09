#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/apps/ai-interview}"
API_LOCAL_PORT="${API_LOCAL_PORT:-18001}"
FRONTEND_LOCAL_PORT="${FRONTEND_LOCAL_PORT:-13000}"
ADMIN_LOCAL_PORT="${ADMIN_LOCAL_PORT:-13001}"
MIN_PUBLIC_PROFILES="${MIN_PUBLIC_PROFILES:-12}"

DO_DEPLOY=0
SKIP_SEED=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/stage79_server_verify.sh [--deploy] [--skip-seed]

Default mode only verifies the running server.
Use --deploy to fetch origin/main, reset server code, rebuild services, run migrations and seed public profiles.

Environment overrides:
  PROJECT_DIR=/opt/apps/ai-interview
  API_LOCAL_PORT=18001
  FRONTEND_LOCAL_PORT=13000
  ADMIN_LOCAL_PORT=13001
  MIN_PUBLIC_PROFILES=12
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

soft_check() {
  local name="$1"
  shift
  echo "+ $*"
  if "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name" >&2
    failures=$((failures + 1))
  fi
}

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
echo "commit: $(git log --oneline -1)"

if [ "$DO_DEPLOY" -eq 1 ]; then
  section "Deploy origin/main"
  run git fetch origin
  run git reset --hard origin/main
  echo "after reset: $(git log --oneline -1)"

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
  grep -E '^(REDIS_HOST|REDIS_PORT|REDIS_PASSWORD|CELERY_BROKER_URL|CELERY_RESULT_BACKEND)=' .env || true
  redis_port="$(grep -E '^REDIS_PORT=' .env | tail -n 1 | cut -d= -f2- | tr -d '"'\''[:space:]' || true)"
  if [ -n "$redis_port" ] && ! printf '%s' "$redis_port" | grep -Eq '^[0-9]+$'; then
    echo "FAIL: REDIS_PORT is not numeric: $redis_port" >&2
    failures=$((failures + 1))
  fi
else
  echo "WARN: .env not found"
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
fi

if [ "${slice_count:-0}" -le 0 ]; then
  echo "FAIL: knowledge slices are empty" >&2
  failures=$((failures + 1))
fi

section "Recent app errors"
docker compose logs --tail=300 app | grep -Ei "Traceback|UndefinedColumn|relation .* does not exist|interviews/start|evaluation-datasets|celery|redis" || true

section "Summary"
if [ "$failures" -eq 0 ]; then
  echo "PASS: server validation checks passed."
  exit 0
fi

echo "FAIL: ${failures} validation check(s) failed." >&2
echo "Next step: copy the first backend traceback or failing command output into the task record." >&2
exit 1
