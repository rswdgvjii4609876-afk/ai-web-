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
git rev-parse HEAD > "$backup_dir/commit.txt"
echo "Private backup saved to $backup_dir"
