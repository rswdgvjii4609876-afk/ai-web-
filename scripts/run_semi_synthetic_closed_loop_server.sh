#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESUME_DIR="${RESUME_DIR:-$ROOT_DIR/docs/competition/datasets/raw-data-resume}"
CONTAINER_INPUT_DIR="/tmp/ai-interview-semi-synthetic-resumes"
RUN_ID="$(date -u +%Y%m%d_%H%M%S)"
OUT_DIR="/app/logs/semi_synthetic_resume_runs/${RUN_ID}"
MODE="actual"
LIMIT=""
ROUNDS="${ROUNDS:-3}"
DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-v4-pro}"
DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
DEEPSEEK_THINKING="${DEEPSEEK_THINKING:-disabled}"
DEEPSEEK_REASONING_EFFORT="${DEEPSEEK_REASONING_EFFORT:-low}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_semi_synthetic_closed_loop_server.sh [--dry-run] [--limit N]

Environment:
  DEEPSEEK_API_KEY   Optional. If set, passed only to the app container process.
  DEEPSEEK_MODEL     Optional. Defaults to deepseek-v4-pro for batch stability.
  DEEPSEEK_BASE_URL  Optional. Defaults to https://api.deepseek.com.
  DEEPSEEK_THINKING  Optional. Defaults to disabled.
  DEEPSEEK_REASONING_EFFORT Optional. Defaults to low.
  RESUME_DIR         Optional. Defaults to docs/competition/datasets/raw-data-resume.
  ROUNDS             Optional. Defaults to 3.

Notes:
  - This script copies local resume files into the running app container /tmp.
  - Outputs are written to ai-interview-backend/logs/semi_synthetic_resume_runs/<timestamp>.
  - Output records remain semi-synthetic: simulated_from_resume + ai_simulated + for_real_sft=false.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ ! -d "$RESUME_DIR" ]]; then
  echo "Resume directory not found: $RESUME_DIR" >&2
  echo "Upload/copy resumes to this directory on the server first." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found. Run this script on the server with Docker Compose installed." >&2
  exit 1
fi

docker compose ps app >/dev/null
docker compose exec -T app sh -lc "rm -rf '$CONTAINER_INPUT_DIR' && mkdir -p '$CONTAINER_INPUT_DIR'"
docker compose cp "$RESUME_DIR/." "app:$CONTAINER_INPUT_DIR"

ARGS=(
  python -m app.scripts.run_resume_closed_loop_batch
  --resume-dir "$CONTAINER_INPUT_DIR"
  --out "$OUT_DIR"
  --rounds "$ROUNDS"
  --contribute-semi-synthetic
)

if [[ -n "$LIMIT" ]]; then
  ARGS+=(--limit "$LIMIT")
fi

if [[ "$MODE" == "dry-run" ]]; then
  ARGS+=(--dry-run)
else
  ARGS+=(--confirm-api-cost)
fi

echo "ai_runtime_model=$DEEPSEEK_MODEL"
echo "ai_runtime_base_url=$DEEPSEEK_BASE_URL"
echo "ai_runtime_thinking=$DEEPSEEK_THINKING"
echo "ai_runtime_reasoning_effort=$DEEPSEEK_REASONING_EFFORT"

EXEC_ARGS=(
  exec -T
  -e DEEPSEEK_MODEL
  -e DEEPSEEK_BASE_URL
  -e DEEPSEEK_THINKING
  -e DEEPSEEK_REASONING_EFFORT
)
if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
  EXEC_ARGS+=(-e DEEPSEEK_API_KEY)
fi

docker compose "${EXEC_ARGS[@]}" app "${ARGS[@]}"
docker compose exec -T app python -m app.scripts.summarize_semi_synthetic_run --run-dir "$OUT_DIR"

echo "host_report_dir=$ROOT_DIR/ai-interview-backend/logs/semi_synthetic_resume_runs/$RUN_ID"
echo "sanitized_summary=$ROOT_DIR/ai-interview-backend/logs/semi_synthetic_resume_runs/$RUN_ID/sanitized_summary.md"
