#!/usr/bin/env bash
set -euo pipefail
echo "Running migrations..."
alembic upgrade head
echo "Seeding..."
python scripts/seed.py || true
exec "$@"
