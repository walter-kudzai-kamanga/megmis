"""Integration tests against PostGIS + Redis (compose or CI services)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    return os.getenv("INTEGRATION", "").lower() in {"1", "true", "yes"}


@pytest.fixture(scope="module")
def integration_env(settings, client, api_keys):
    if not _integration_enabled():
        pytest.skip("Set INTEGRATION=1 with PostGIS+Redis available")
    if not settings.use_persistence:
        pytest.skip("USE_PERSISTENCE must be true for integration tests")
    return client, settings, api_keys


def test_redis_weather_cache_roundtrip(integration_env):
    client, settings, api_keys = integration_env
    headers = {"X-API-Key": api_keys["a"]}
    r1 = client.get("/api/v1/weather/current?name=Harare", headers=headers)
    r2 = client.get("/api/v1/weather/current?name=Harare", headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["data"]["temperature_c"] == r2.json()["data"]["temperature_c"]

    from megmis.db.session import get_redis

    keys = list(get_redis().scan_iter("weather:*"))
    assert keys, "expected weather cache keys in Redis"


def test_route_persisted_and_journey_isolated(integration_env):
    client, settings, api_keys = integration_env
    headers_a = {"X-API-Key": api_keys["a"]}
    headers_b = {"X-API-Key": api_keys["b"]}

    opt = client.post(
        "/api/v1/routes/optimize",
        headers=headers_a,
        json={
            "origin": {"name": "Harare"},
            "destination": {"name": "Bulawayo"},
            "profile": "safest",
        },
    )
    assert opt.status_code == 200
    route_id = opt.json()["data"]["route_id"]

    from megmis.db.models import Route
    from megmis.db.session import session_scope

    with session_scope() as session:
        session.execute(text("SELECT set_config('app.tenant_id', '', true)"))
        row = session.scalar(select(Route).where(Route.id == uuid.UUID(route_id)))
        assert row is not None
        assert row.result.get("routes")

    created = client.post("/api/v1/journeys", headers=headers_a, json={"route_id": route_id})
    assert created.status_code == 201
    jid = created.json()["data"]["id"]
    assert client.get(f"/api/v1/journeys/{jid}", headers=headers_b).status_code == 404


def test_db_seed_zimbabwe_locations(integration_env):
    from megmis.db.models import Location
    from megmis.db.session import session_scope

    with session_scope() as session:
        count = len(list(session.scalars(select(Location)).all()))
    assert count >= 5


def test_postgis_extension(integration_env):
    from megmis.db.session import get_engine

    with get_engine().connect() as conn:
        version = conn.execute(text("select postgis_version()")).scalar()
    assert version and "3." in version
