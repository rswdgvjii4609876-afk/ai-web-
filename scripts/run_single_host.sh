#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo "Docker Engine is required." >&2; exit 1; }
docker compose version >/dev/null
test -f .env || { echo "Run python3 scripts/init_runtime_env.py --admin-email YOUR_EMAIL first." >&2; exit 1; }
compose=(docker compose -f compose.single-host.yml)
"${compose[@]}" config --quiet
# Build one image at a time to reduce peak memory on a 2 GB host.
"${compose[@]}" build app
"${compose[@]}" build frontend
"${compose[@]}" build admin
"${compose[@]}" up -d --no-build --wait --wait-timeout 240
python3 scripts/check_runtime.py
"${compose[@]}" ps
