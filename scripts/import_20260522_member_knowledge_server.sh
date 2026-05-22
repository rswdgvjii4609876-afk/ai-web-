#!/usr/bin/env bash
set -euo pipefail

PACKAGE_SOURCE="/app/app/data/knowledge_packages/member_submissions/2026-05-22"
APP_ROOT="/opt/apps/ai-interview"
RUN_MODE="dry-run"

usage() {
  cat <<'USAGE'
Usage:
  scripts/import_20260522_member_knowledge_server.sh [--execute]

Default mode is dry-run:
  - pull latest code
  - rebuild services
  - run alembic
  - audit current position knowledge state
  - validate the 2026-05-22 package
  - run import dry-run
  - run merge dry-run

Use --execute only after dry-run output is correct:
  - import the package
  - merge legacy member supplement profiles
  - run usage and strict audit checks
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --execute)
      RUN_MODE="execute"
      shift
      ;;
    -h|--help)
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

cd "$APP_ROOT"

echo "[1/8] Pull latest code"
git pull

echo "[2/8] Rebuild and migrate"
docker compose up -d --build
docker compose exec -T app alembic upgrade head

echo "[3/8] Audit current position knowledge state"
docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict

echo "[4/8] Validate 2026-05-22 package"
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages \
  --source "$PACKAGE_SOURCE" \
  --check-only

echo "[5/8] Import dry-run"
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages \
  --source "$PACKAGE_SOURCE" \
  --dry-run \
  --create-missing-canonical \
  --activate-created-canonical

echo "[6/8] Legacy supplement merge dry-run"
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run

if [ "$RUN_MODE" != "execute" ]; then
  cat <<'NEXT'

Dry-run complete. Review the output above.
If the target profiles and merge plan are correct, run:

  scripts/import_20260522_member_knowledge_server.sh --execute

NEXT
  exit 0
fi

echo "[7/8] Execute import and merge"
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages \
  --source "$PACKAGE_SOURCE" \
  --create-missing-canonical \
  --activate-created-canonical
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases

echo "[8/8] Verify usage and final strict audit"
docker compose exec -T app python -m app.scripts.check_member_knowledge_usage \
  --source "$PACKAGE_SOURCE" \
  --database
docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict

echo "2026-05-22 member knowledge import and canonical merge completed."
