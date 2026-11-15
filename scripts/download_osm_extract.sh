#!/usr/bin/env bash
# Download a small Zimbabwe OSM extract (Geofabrik) for local routing graph builds.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/data/osm"
mkdir -p "$OUT_DIR"

# Full Zimbabwe PBF from Geofabrik (~50MB). Optional — Gen 1 ships a minimal .osm.
URL="${OSM_URL:-https://download.geofabrik.de/africa/zimbabwe-latest.osm.pbf}"
OUT="$OUT_DIR/zimbabwe-latest.osm.pbf"

echo "Fetching $URL"
if command -v curl >/dev/null; then
  curl -L --fail --retry 3 -o "$OUT" "$URL"
elif command -v wget >/dev/null; then
  wget -O "$OUT" "$URL"
else
  echo "curl or wget required" >&2
  exit 1
fi

echo "Saved $OUT"
ls -lh "$OUT"
