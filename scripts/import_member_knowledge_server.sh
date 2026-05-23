#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/apps/ai-interview}"
PACKAGE_DATE=""
RUN_MODE="dry-run"
RUN_STARTED="$(date -u +%Y%m%d_%H%M%S)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/import_member_knowledge_server.sh --package-date YYYY-MM-DD [--execute|--verify-only]

Default mode is dry-run:
  - pull latest code
  - rebuild services
  - run alembic
  - audit current position knowledge state without blocking remediation
  - validate the package
  - run import dry-run
  - run legacy supplement merge dry-run

Use --execute only after dry-run output is correct:
  - import the package
  - merge legacy member supplement profiles
  - run usage, package-position and strict audit checks

Use --verify-only after execution to re-check database state without git pull, build, migrate or import.
USAGE
}

package_source() {
  echo "/app/app/data/knowledge_packages/member_submissions/${PACKAGE_DATE}"
}

host_package_source() {
  echo "$APP_ROOT/ai-interview-backend/app/data/knowledge_packages/member_submissions/${PACKAGE_DATE}"
}

package_json_path() {
  echo "$(package_source)/member_interview_experience_package.json"
}

host_package_json_path() {
  echo "$(host_package_source)/member_interview_experience_package.json"
}

assert_host_package_exists() {
  local host_json
  host_json="$(host_package_json_path)"
  if [ ! -f "$host_json" ]; then
    cat >&2 <<ERR
Package file does not exist on the server host:
  $host_json

This script imports package files from the server checkout, then copies them into the app container.
Make sure the ${PACKAGE_DATE} package directory has been committed/pushed and pulled on this server,
or copy it to:
  $(host_package_source)
ERR
    exit 3
  fi
}

sync_package_to_container() {
  local host_source
  local container_source
  host_source="$(host_package_source)"
  container_source="$(package_source)"
  assert_host_package_exists
  echo "[package] Sync ${PACKAGE_DATE} package into app container"
  docker compose exec -T app mkdir -p "$container_source"
  docker compose cp "$host_source/." "app:$container_source/"
}

package_expected_sql_values() {
  docker compose exec -T app python - "$(package_json_path)" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8-sig"))
positions = sorted(
    {
        str(item.get("target_position", "")).strip()
        for item in payload.get("items", [])
        if isinstance(item, dict) and str(item.get("target_position", "")).strip()
    }
)
if not positions:
    raise SystemExit(f"no package target positions found: {path}")
print(", ".join("('" + position.replace("'", "''") + "')" for position in positions))
PY
}

print_package_positions() {
  docker compose exec -T app python - "$(package_json_path)" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8-sig"))
positions = sorted(
    {
        str(item.get("target_position", "")).strip()
        for item in payload.get("items", [])
        if isinstance(item, dict) and str(item.get("target_position", "")).strip()
    }
)
print("package_positions=" + json.dumps(positions, ensure_ascii=False))
PY
}

run_final_verification() {
  local package_source
  local expected_values
  package_source="$(package_source)"

  sync_package_to_container

  echo "[verification] Package positions"
  print_package_positions
  expected_values="$(package_expected_sql_values)"

  echo "[verification] Usage check"
  docker compose exec -T app python -m app.scripts.check_member_knowledge_usage \
    --source "$package_source" \
    --database

  echo "[verification] Active legacy member supplement profiles should be 0"
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh -c "
select count(*) as active_member_supplements
from position_knowledge_bases
where scope = 'public'
  and is_active = true
  and title like '成员资料补充：%';
"

  echo "[verification] Enabled interview_experience slice counts for package target positions"
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh -c "
with expected(target_position) as (
  values ${expected_values}
)
select e.target_position, kb.title, count(s.id) as interview_experience_slices
from expected e
left join position_knowledge_bases kb
  on kb.target_position = e.target_position
 and kb.scope = 'public'
 and kb.is_active = true
 and kb.title = '职启智评岗位画像：' || e.target_position
left join position_knowledge_base_slices s
  on s.knowledge_base_id = kb.id
 and s.source_section = 'interview_experience'
 and s.is_enabled = true
group by e.target_position, kb.title
order by e.target_position;
"

  echo "[verification] Package-specific hard checks"
  docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh -v ON_ERROR_STOP=1 -c "
do \$\$
declare
  active_supplement_count integer;
  invalid_profile_positions text;
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
    values ${expected_values}
  ),
  profile_counts as (
    select e.target_position, count(kb.id) as profile_count
    from expected e
    left join position_knowledge_bases kb
      on kb.target_position = e.target_position
     and kb.scope = 'public'
     and kb.is_active = true
     and kb.title = '职启智评岗位画像：' || e.target_position
    group by e.target_position
  )
  select string_agg(target_position || '=' || profile_count::text, ', ' order by target_position)
    into invalid_profile_positions
  from profile_counts
  where profile_count <> 1;

  if invalid_profile_positions is not null then
    raise exception 'expected exactly one active canonical profile for package positions: %', invalid_profile_positions;
  end if;

  with expected(target_position) as (
    values ${expected_values}
  ),
  counts as (
    select e.target_position, count(s.id) as slice_count
    from expected e
    left join position_knowledge_bases kb
      on kb.target_position = e.target_position
     and kb.scope = 'public'
     and kb.is_active = true
     and kb.title = '职启智评岗位画像：' || e.target_position
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
    raise exception 'missing enabled interview_experience slices for package positions: %', missing_slice_positions;
  end if;
end
\$\$;
"

  echo "[verification] Final strict audit"
  docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync --strict
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --package-date)
      shift
      if [ "$#" -eq 0 ]; then
        echo "--package-date requires YYYY-MM-DD" >&2
        exit 2
      fi
      PACKAGE_DATE="$1"
      shift
      ;;
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

if [ -z "$PACKAGE_DATE" ]; then
  echo "--package-date is required" >&2
  usage >&2
  exit 2
fi

case "$PACKAGE_DATE" in
  ????-??-??) ;;
  *)
    echo "--package-date must use YYYY-MM-DD: $PACKAGE_DATE" >&2
    exit 2
    ;;
esac

cd "$APP_ROOT"
COMPACT_DATE="${PACKAGE_DATE//-/}"
LOG_DIR="$APP_ROOT/ai-interview-backend/logs/member_knowledge_imports"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/${COMPACT_DATE}_${RUN_MODE}_${RUN_STARTED}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "log_file=$LOG_FILE"
echo "package_date=$PACKAGE_DATE"
echo "run_mode=$RUN_MODE"

if [ "$RUN_MODE" = "verify-only" ]; then
  assert_host_package_exists
  run_final_verification
  echo "result=VERIFY_PASS"
  exit 0
fi

PACKAGE_SOURCE="$(package_source)"

echo "[1/8] Pull latest code"
git pull
assert_host_package_exists

echo "[2/8] Rebuild and migrate"
docker compose up -d --build
docker compose exec -T app alembic upgrade head

echo "[3/8] Audit current position knowledge state"
docker compose exec -T app python -m app.scripts.audit_position_knowledge_sync

echo "[4/8] Validate ${PACKAGE_DATE} package"
sync_package_to_container
print_package_positions
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages \
  --source "$PACKAGE_SOURCE" \
  --check-only
echo "result=CHECK_PASS"

echo "[5/8] Import dry-run"
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages \
  --source "$PACKAGE_SOURCE" \
  --dry-run \
  --create-missing-canonical \
  --activate-created-canonical

echo "[6/8] Legacy supplement merge dry-run"
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run
echo "result=DRY_RUN_PASS"

if [ "$RUN_MODE" != "execute" ]; then
  cat <<NEXT

Dry-run complete. Review the output above.
If the target profiles and merge plan are correct, run:

  scripts/import_member_knowledge_server.sh --package-date ${PACKAGE_DATE} --execute

NEXT
  exit 0
fi

echo "[7/8] Execute import and merge"
docker compose exec -T app python -m app.scripts.import_member_knowledge_packages \
  --source "$PACKAGE_SOURCE" \
  --create-missing-canonical \
  --activate-created-canonical
docker compose exec -T app python -m app.scripts.merge_member_supplement_knowledge_bases
echo "result=MERGE_PASS"

echo "[8/8] Verify usage and final strict audit"
run_final_verification
echo "result=IMPORT_PASS"
echo "${PACKAGE_DATE} member knowledge import and canonical merge completed."
