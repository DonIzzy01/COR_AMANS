#!/bin/sh
set -e

echo "→ Initialising database tables…"
python -c "from app import init_db; init_db()"
echo "→ Database ready."

exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  app:app
