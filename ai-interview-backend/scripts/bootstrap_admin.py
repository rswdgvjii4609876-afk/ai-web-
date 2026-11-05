"""Prompt for the first admin password inside a running backend container."""
import asyncio
import getpass
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from app.core.config import settings
    from scripts.create_first_admin import create_first_admin, _validate_password
    password = getpass.getpass("Initial administrator password: ")
    _validate_password(password)
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    os.environ["INIT_ADMIN_EMAIL"] = settings.ROOT_ADMIN_EMAIL
    os.environ["INIT_ADMIN_PASSWORD"] = password
    asyncio.run(create_first_admin())


if __name__ == "__main__":
    main()
