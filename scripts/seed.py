#!/usr/bin/env python3
"""Seed Zimbabwe regions, tenants, incidents, and ensure OSM extract exists."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geoalchemy2.elements import WKTElement  # noqa: E402
from sqlalchemy import select  # noqa: E402

from megmis.common.auth import hash_api_key, seed_dev_key  # noqa: E402
from megmis.common.zimbabwe import KNOWN_PLACES  # noqa: E402
from megmis.config import get_settings  # noqa: E402
from megmis.db.models import Incident, Location  # noqa: E402
from megmis.db.session import session_scope  # noqa: E402

OSM_MINIMAL = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='megmis-seed'>
  <node id='1' lat='-17.8252' lon='31.0335'/>
  <node id='2' lat='-18.5' lon='30.0'/>
  <node id='3' lat='-19.5' lon='29.2'/>
  <node id='4' lat='-20.1325' lon='28.6265'/>
  <node id='5' lat='-18.9707' lon='32.6709'/>
  <way id='10'>
    <nd ref='1'/><nd ref='2'/><nd ref='3'/><nd ref='4'/>
    <tag k='highway' v='trunk'/>
    <tag k='name' v='A5 Harare-Bulawayo'/>
    <tag k='ref' v='A5'/>
  </way>
  <way id='11'>
    <nd ref='1'/><nd ref='5'/>
    <tag k='highway' v='primary'/>
    <tag k='name' v='A3 Harare-Mutare'/>
    <tag k='ref' v='A3'/>
  </way>
</osm>
"""


def ensure_osm_extract(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        print(f"OSM extract present: {path}")
        return
    path.write_text(OSM_MINIMAL)
    print(f"Wrote minimal Zimbabwe corridor OSM extract: {path}")
    readme = path.parent / "README.md"
    if not readme.exists():
        readme.write_text(
            "# OSM extracts\n\n"
            "`zimbabwe-harare-bulawayo.osm` is a Gen 1 placeholder graph covering "
            "Harare–Bulawayo (A5) and Harare–Mutare (A3).\n\n"
            "To replace with a real extract:\n\n"
            "```bash\n"
            "./scripts/download_osm_extract.sh\n"
            "```\n"
        )


def seed_locations_and_incidents() -> None:
    with session_scope() as session:
        for name, (lat, lon) in KNOWN_PLACES.items():
            display = name.title()
            existing = session.scalar(
                select(Location).where(Location.name == display, Location.tenant_id.is_(None))
            )
            if existing:
                continue
            session.add(
                Location(
                    tenant_id=None,
                    name=display,
                    lat=lat,
                    lon=lon,
                    geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                    admin_area="Zimbabwe",
                )
            )

        seeds = [
            ("flood", 4, 0.85, True, -19.2, 29.0, "Harare-Bulawayo"),
            ("pothole", 2, 0.25, False, -18.5, 31.5, "Harare-Mutare"),
            ("damaged_road", 3, 0.7, False, -19.8, 29.5, "Harare-Bulawayo"),
        ]
        for typ, sev, conf, verified, lat, lon, area in seeds:
            exists = session.scalar(
                select(Incident).where(Incident.type == typ, Incident.area == area)
            )
            if exists:
                continue
            session.add(
                Incident(
                    source="seed",
                    type=typ,
                    severity=sev,
                    confidence=conf,
                    verified=verified,
                    status="active",
                    area=area,
                    lat=lat,
                    lon=lon,
                    geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                )
            )
    print("Seeded shared Zimbabwe locations + corridor incidents")


def main() -> None:
    settings = get_settings()
    ensure_osm_extract(ROOT / settings.osm_extract_path)
    seed_dev_key(settings)
    seed_locations_and_incidents()
    print("Seed complete.")
    print(f"  demo key: {settings.dev_api_key}")
    print(f"  tenant-b key: {settings.dev_api_key_b}")
    print(f"  demo key hash: {hash_api_key(settings.dev_api_key)[:12]}...")


if __name__ == "__main__":
    main()
