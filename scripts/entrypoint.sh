#!/bin/sh
set -e
# Celery workers/beat: no migrate/collectstatic (web handles that first).
if [ "$1" = "celery" ]; then
  exec "$@"
fi
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
