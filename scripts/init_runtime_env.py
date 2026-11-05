"""Generate a private, non-overwriting single-host preview configuration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def initialize(output: Path, admin_email: str) -> None:
    if not admin_email or "@" not in admin_email or any(c in admin_email for c in "\r\n'\"$# "):
        raise ValueError("Provide a plain admin email address without whitespace or dotenv syntax")
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for marker in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "SECRET_KEY", "LLM_SECRET"):
        text = text.replace(f"<GENERATE_{marker}>", secrets.token_hex(32))
    text = text.replace("owner@example.com", admin_email.strip().lower())
    # O_EXCL prevents accidental rotation of the key used to decrypt user API keys.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--admin-email", required=True)
    args = parser.parse_args()
    try:
        initialize(args.output, args.admin_email)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Configuration not written: {exc}\n")
    print(f"Private configuration created: {args.output}")
    print("Preview mode, loopback-only ports. Existing secrets were not printed.")


if __name__ == "__main__":
    main()
