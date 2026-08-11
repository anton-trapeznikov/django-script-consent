#!/bin/sh
set -e

echo "→ Applying migrations..."
python example_project/manage.py migrate --noinput

# Fail fast if schema is out of date (e.g. old named volume after model rename).
python <<'PY'
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")
django.setup()

from django.db import connection
from django.db.utils import OperationalError

required = (
    "script_consent_scriptcategory",
    "script_consent_scriptsnippet",
    "script_consent_bannerconfig",
)
with connection.cursor() as cursor:
    existing = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
missing = [t for t in required if t not in existing]
if missing:
    print(
        "ERROR: expected tables missing after migrate:",
        ", ".join(missing),
        file=sys.stderr,
    )
    print(
        "If you renamed models while reusing a Docker volume, reset it:\n"
        "  docker compose down -v && docker compose up --build",
        file=sys.stderr,
    )
    sys.exit(1)
print("  schema ok:", ", ".join(required))
PY

echo "→ Ensuring demo superuser (if credentials provided)..."
python <<'PY'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com").strip()

if username and password:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_staff": True, "is_superuser": True},
    )
    if created:
        user.set_password(password)
        user.save()
        print(f"  created superuser '{username}'")
    else:
        # Keep existing user; update password only if CREATE forces? leave as-is
        if not user.is_superuser or not user.is_staff:
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=["is_superuser", "is_staff"])
        print(f"  superuser '{username}' already exists")
else:
    print("  skipped (set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD)")
PY

echo "→ Starting: $*"
exec "$@"
