"""Attach the preview frontends to an existing Caddy, with config rollback."""
import argparse
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "# BEGIN AI_INTERVIEW_PREVIEW_HTTPS"
END = "# END AI_INTERVIEW_PREVIEW_HTTPS"


def run(*args, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True,
                          capture_output=capture)


def site(host, upstream):
    return f"""{host} {{
    tls {{
        issuer acme
    }}
    encode gzip zstd
    reverse_proxy {upstream}:80 {{
        flush_interval -1
    }}
}}
"""


def update_config(original, frontend, admin):
    if original.count(BEGIN) != original.count(END) or original.count(BEGIN) > 1:
        raise ValueError("Unexpected gateway marker structure; no configuration written")
    clean = original
    if BEGIN in original:
        first = original.index(BEGIN)
        last = original.index(END, first) + len(END)
        clean = original[:first] + original[last:]
    if frontend in clean or admin in clean:
        raise ValueError("A requested hostname already belongs to another configuration")
    return (clean.rstrip() + "\n\n" + BEGIN + "\n"
            + site(frontend, "ai-interview-preview-web") + "\n"
            + site(admin, "ai-interview-preview-admin") + END + "\n")


def curl(host, path):
    return subprocess.run([
        "curl", "--fail", "--silent", "--show-error", "--max-time", "12",
        "--noproxy", "*", "--resolve", f"{host}:443:127.0.0.1",
        f"https://{host}{path}"], capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caddy", required=True)
    parser.add_argument("--network", required=True)
    parser.add_argument("--server-ip", required=True)
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--admin", required=True)
    args = parser.parse_args()
    for value in (args.caddy, args.network):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Invalid Docker name")
    for host in (args.frontend, args.admin):
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            raise ValueError("Invalid hostname")
        ips = {entry[4][0] for entry in socket.getaddrinfo(host, 443)}
        if args.server_ip not in ips:
            raise ValueError(f"{host} does not resolve to the specified server IP")
    if args.frontend == args.admin:
        raise ValueError("Frontend and admin hostnames must differ")

    inspect = json.loads(run("docker", "inspect", args.caddy, capture=True).stdout)[0]
    if args.network not in inspect["NetworkSettings"]["Networks"]:
        raise ValueError("The selected Caddy is not attached to the selected network")
    mounts = [m for m in inspect["Mounts"] if m["Destination"] == "/etc/caddy/Caddyfile"]
    if len(mounts) != 1:
        raise ValueError("Expected one persistent Caddyfile mount")
    config_path = Path(mounts[0]["Source"])
    if not config_path.is_file() or config_path.is_symlink():
        raise ValueError("Expected a regular, host-mounted Caddyfile")
    original_bytes = config_path.read_bytes()
    original = original_bytes.decode("utf-8")
    new_config = update_config(original, args.frontend, args.admin)
    backup = config_path.with_name(config_path.name + ".ai-interview-backup-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(config_path, backup)
    print(f"Existing gateway configuration backed up: {backup}", flush=True)

    overlay = ROOT / "compose.gateway.yml"
    if overlay.exists():
        shutil.copy2(overlay, ROOT / ("compose.gateway.yml.backup-" + time.strftime("%Y%m%d-%H%M%S")))
    overlay.write_text((ROOT / "compose.gateway.yml.example").read_text().replace(
        "__GATEWAY_NETWORK__", args.network), encoding="utf-8")
    compose = ["docker", "compose", "-f", "compose.single-host.yml", "-f", "compose.gateway.yml"]
    run(*compose, "config", "--quiet")
    run(*compose, "up", "-d", "--no-build", "--no-deps", "frontend", "admin")

    wrote_config = False
    try:
        # Preserve the inode: Caddy uses a file bind mount, not a directory mount.
        wrote_config = True
        config_path.write_text(new_config, encoding="utf-8")
        run("docker", "exec", args.caddy, "caddy", "validate", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile")
        run("docker", "exec", args.caddy, "caddy", "reload", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile")
        print("Waiting for trusted HTTPS certificates (up to 4 minutes)...", flush=True)
        pending = {args.frontend, args.admin}
        deadline = time.monotonic() + 240
        last_error = ""
        while pending and time.monotonic() < deadline:
            for host in tuple(pending):
                result = curl(host, "/healthz")
                if result.returncode == 0 and result.stdout.strip() == "ok":
                    pending.remove(host)
                    print(f"HTTPS PASS: {host}", flush=True)
                else:
                    last_error = result.stderr[-400:]
            if pending:
                print("Still waiting for: " + ", ".join(sorted(pending)), flush=True)
                time.sleep(10)
        if pending:
            raise RuntimeError("HTTPS did not become ready: " + last_error)
        for host in (args.frontend, args.admin):
            result = curl(host, "/api/v1/config/health")
            if result.returncode:
                raise RuntimeError("Gateway API probe failed: " + result.stderr[-300:])
            services = json.loads(result.stdout)["data"]["services"]
            if any(services.get(s) != "up" for s in ("api", "database", "redis", "migrations")):
                raise RuntimeError("Gateway backend readiness check failed")
    except BaseException:
        if wrote_config:
            config_path.write_bytes(original_bytes)
            try:
                run("docker", "exec", args.caddy, "caddy", "reload", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile")
                print("Original gateway configuration restored.", file=sys.stderr)
            except Exception:
                print(f"Gateway recovery requires attention; backup: {backup}", file=sys.stderr)
        raise
    print("HTTPS_GATEWAY_PASS")
    print("User: https://" + args.frontend)
    print("Admin: https://" + args.admin)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print("Gateway setup stopped: " + str(exc), file=sys.stderr)
        sys.exit(1)
