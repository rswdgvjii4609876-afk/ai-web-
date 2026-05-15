"""Deprecated admin seeding entrypoint.

Do not create default backoffice accounts with hard-coded passwords.
Use ``scripts/create_first_admin.py`` with INIT_ADMIN_EMAIL and
INIT_ADMIN_PASSWORD environment variables instead.
"""

raise SystemExit(
    "app.scripts.seed_admin is deprecated. Use scripts/create_first_admin.py "
    "with INIT_ADMIN_EMAIL and INIT_ADMIN_PASSWORD."
)
