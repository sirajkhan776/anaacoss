#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-render-build-only-secret-key-change-at-runtime-1234567890}"
python manage.py migrate --noinput
python manage.py ensure_admin_user
# Dummy/seed data loading is intentionally disabled in production builds.
# if [ "${DJANGO_LOAD_INITIAL_DATA:-0}" = "1" ]; then
#   python manage.py load_data
# fi
# if [ "${DJANGO_LOAD_FIXTURES:-0}" = "1" ] && [ -f data.json ]; then
#   python manage.py loaddata data.json
# fi
python manage.py collectstatic --noinput
