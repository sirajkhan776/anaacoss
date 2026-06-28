#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-render-build-only-secret-key-change-at-runtime-1234567890}"
# Render build containers do not have the runtime disk mounted at /var/data.
# Always use a writable local SQLite file during build; runtime can still use
# SQLITE_PATH=/var/data/db.sqlite3 from the service environment.
export SQLITE_PATH="$PWD/db.sqlite3"
python manage.py migrate --noinput
python manage.py ensure_admin_user
python manage.py collectstatic --noinput
