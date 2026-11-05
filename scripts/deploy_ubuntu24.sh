#!/usr/bin/env bash
# Run from the authenticated Tencent Cloud terminal on Ubuntu 24.04.
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup_access() {
  set +e
  systemctl stop codex-deploy-ssh.service >/dev/null 2>&1
  local keys=/root/.ssh/authorized_keys
  if [[ -f "$keys" && ! -L "$keys" ]] && grep -qF codex-ai-interview-deploy-01a1aaeb "$keys"; then
    local clean
    clean=$(mktemp /root/.ssh/.codex-keys.XXXXXX)
    chmod 600 "$clean"
    awk 'index($0,"codex-ai-interview-deploy-01a1aaeb")==0' "$keys" > "$clean"
    mv "$clean" "$keys"
  fi
  rm -f /run/codex-deploy-keys /run/codex-deploy-ssh.pid
}

on_exit() {
  local result=$?
  cleanup_access
  if (( result != 0 )); then
    echo "Deployment stopped (exit $result). Preserve .env and volumes; share the error output."
  fi
  exit "$result"
}

[[ $EUID -eq 0 ]] || { echo "Run this script with sudo bash." >&2; exit 1; }
trap on_exit EXIT
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || {
  echo "This installer requires Ubuntu 24.04." >&2; exit 1;
}
echo "Checking host resources and existing listeners..."
free -h
df -h .
ss -lnt

apt-get update
apt-get install -y ca-certificates curl python3
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/ai-interview-docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
docker compose version || {
  echo "Existing Docker has no Compose plugin; stopped without replacing Docker." >&2; exit 1;
}
if ! docker info >/dev/null 2>&1; then
  systemctl enable --now docker
fi

if [[ ! -f .env ]]; then
  read -r -p "Administrator email: " admin_email </dev/tty
  python3 scripts/init_runtime_env.py --admin-email "$admin_email"
  python3 - <<'PY'
from pathlib import Path
p = Path('.env')
p.write_text(p.read_text().replace('COMPOSE_PROJECT_NAME=ai-interview\n', 'COMPOSE_PROJECT_NAME=ai-interview-preview\n'))
PY
fi

compose=(docker compose -f compose.single-host.yml)
"${compose[@]}" config --quiet
project_name=$("${compose[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')
ids=$(docker ps -aq --filter "label=com.docker.compose.project=$project_name")
for id in $ids; do
  workdir=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$id")
  [[ "$workdir" == "$PWD" ]] || {
    echo "Compose project $project_name belongs to another directory: $workdir" >&2; exit 1;
  }
done
if [[ -z "$ids" ]] && ss -H -lnt '( sport = :8080 or sport = :8081 )' | grep -q .; then
  echo "8080 or 8081 belongs to an existing service. Stopped without changing it." >&2
  exit 1
fi

bash scripts/run_single_host.sh
echo "Create the administrator, or press Ctrl+C to finish later."
"${compose[@]}" exec app python scripts/bootstrap_admin.py
python3 scripts/check_runtime.py
docker stats --no-stream $("${compose[@]}" ps -q)
echo "PREVIEW_DEPLOYMENT_PASS"
echo "Web ports are loopback-only: 8080 (user), 8081 (admin)."
echo "Temporary deployment SSH authorization will now be removed."
