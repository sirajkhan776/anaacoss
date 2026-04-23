#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-render-build-only-secret-key-change-at-runtime-1234567890}"
python manage.py migrate --noinput
if [ -f data.json ]; then
  python manage.py loaddata data.json
fi
python manage.py collectstatic --noinput
