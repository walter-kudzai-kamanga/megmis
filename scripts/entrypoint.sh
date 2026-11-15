#!/usr/bin/env bash
set -euo pipefail

# Stateless / prototype hosts (Render free, local smoke) skip DB bootstrap.
if [[ "${USE_PERSISTENCE:-true}" == "true" ]]; then
  echo "Running migrations..."
  alembic upgrade head
  echo "Seeding..."
  python scripts/seed.py || true
else
  echo "USE_PERSISTENCE=false — skipping migrations/seed"
fi

exec "$@"
