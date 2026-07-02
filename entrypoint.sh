#!/bin/sh
set -e

echo "→ Initialising database tables…"
python -c "from app import init_db; init_db()"
echo "→ Database ready."

exec gunicorn --config gunicorn.conf.py app:app
