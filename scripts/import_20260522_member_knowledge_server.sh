#!/usr/bin/env bash
set -euo pipefail

PACKAGE_SOURCE="/app/app/data/knowledge_packages/member_submissions/2026-05-22"
APP_ROOT="/opt/apps/ai-interview"
RUN_MODE="dry-run"
RUN_STARTED="$(date -u +%Y%m%d_%H%M%S)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/import_20260522_member_knowledge_server.sh [--execute|--verify-only]

Default mode is dry-run:
  - pull latest code
  - rebuild services
  - run alembic
  - audit current position knowledge state without blocking remediation
  - validate the 2026-05-22 package
  - run import dry-run
  - run merge dry-run

Use --execute only after dry-run output is correct:
  - import the package
  - merge legacy member supplement profiles
  - run usage and strict audit checks

Use --verify-only after execution to re-check the database state without importing again.
USAGE
}

run_final_verification() {
  echo "[verification] Usage check"
  docker compose exec -T app python -m app.scripts.check_member_knowledge_usage \
    --source "$PACKAGE_SOURCE" \
    --database

  echo "[verification] Active legacy member supplement profiles should be 0"
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh -c "
select count(*) as active_member_supplements
from position_knowledge_bases
where scope = 'public'
  and is_active = true
  and title like '成员资料补充：%';
"

  echo "[verification] Enabled interview_experience slice counts for 2026-05-22 target positions"
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh -c "
select kb.target_position, kb.title, count(s.id) as interview_experience_slices
from position_knowledge_bases kb
left join position_knowledge_base_slices s
  on s.knowledge_base_id = kb.id
 and s.source_section = 'interview_experience'
 and s.is_enabled = true
where kb.scope = 'public'
  and kb.is_active = true
  and kb.target_position in ('产品助理', '运营助理', '新媒体运营', '人力资源专员', '招聘助理', '行政管理助理')
group by kb.id
order by kb.target_position;
"

  echo "[verification] Package-specific hard checks"
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh -v ON_ERROR_STOP=1 -c "
do \$\$
declare
  active_supplement_count integer;
  missing_slice_positions text;
begin
  select count(*) into active_supplement_count
  from position_knowledge_bases
  where scope = 'public'
    and is_active = true
    and title like '成员资料补充：%';

  if active_supplement_count <> 0 then
    raise exception 'active member supplement profiles remain: %', active_supplement_count;
  end if;

  with expected(target_position) as (
    values ('产品助理'), ('运营助理'), ('新媒体运营'), ('人力资源专员'), ('招聘助理'), ('行政管理助理')
  ),
  counts as (
    select e.target_position, count(s.id) as slice_count
    from expected e
    left join position_knowledge_bases kb
      on kb.target_position = e.target_position
     and kb.scope = 'public'
     and kb.is_active = true
     and kb.title not like '成员资料补充：%'
     and kb.title not like '历史补充资料（已合并）：%'
    left join position_knowledge_base_slices s
      on s.knowledge_base_id = kb.id
     and s.source_section = 'interview_experience'
     and s.is_enabled = true
    group by e.target_position
  )
  select string_agg(target_position || '=' || slice_count::text, ', ' order by target_position)
    into missing_slice_positions
  from counts
  where slice_count = 0;

  if missing_slice_positions is not null then
    raise exception 'missing enabled interview_experience slices for 2026-05-22 positions: %', missing_slice_positions;
  end if;
end
\$\$;
"

  echo "[verification] Final strict audit"
  docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --execute)
      RUN_MODE="execute"
      shift
      ;;
    --verify-only)
      RUN_MODE="verify-only"
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
LOG_DIR="$APP_ROOT/ai-interview-backend/logs/member_knowledge_imports"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/20260522_${RUN_MODE}_${RUN_STARTED}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "log_file=$LOG_FILE"

if [ "$RUN_MODE" = "verify-only" ]; then
  run_final_verification
  exit 0
fi

echo "[1/8] Pull latest code"
git pull

echo "[2/8] Rebuild and migrate"
docker compose up -d --build
docker compose exec -T app alembic upgrade head

echo "[3/8] Audit current position knowledge state"
docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync

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
run_final_verification

echo "2026-05-22 member knowledge import and canonical merge completed."
