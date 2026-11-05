#!/usr/bin/env bash
# Run during a quiet period; do not upload the resulting private backup to Git.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
test -f .env
compose=(docker compose -f compose.single-host.yml)
backup_dir="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$backup_dir"
"${compose[@]}" exec -T postgres sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_dir/database.dump"
"${compose[@]}" exec -T app tar -C /app -czf - uploads > "$backup_dir/uploads.tar.gz"
cp .env "$backup_dir/runtime.env"
if git rev-parse HEAD > "$backup_dir/commit.txt" 2>/dev/null; then
  :
elif [[ -f DEPLOY_COMMIT.txt ]]; then
  cp DEPLOY_COMMIT.txt "$backup_dir/commit.txt"
else
  echo "unknown-source-version" > "$backup_dir/commit.txt"
fi
echo "Private backup saved to $backup_dir"
