from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Deep Gen 1 stack: INTEGRATION=1 keeps USE_PERSISTENCE from the environment.
# Default unit runs force memory fallbacks.
os.environ.setdefault("AUTH_DISABLED", "false")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")
_INTEGRATION = os.environ.get("INTEGRATION", "").lower() in {"1", "true", "yes"}
if not _INTEGRATION:
    os.environ["USE_PERSISTENCE"] = "false"
else:
    os.environ.setdefault("USE_PERSISTENCE", "true")


@pytest.fixture(scope="session")
def settings():
    from megmis.config import get_settings
    from megmis.db.session import reset_db_caches

    get_settings.cache_clear()
    reset_db_caches()
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def _prepare_persistence(settings):
    """When integration/deep mode is on, migrate + seed before any tests."""
    if not settings.use_persistence:
        yield
        return

    from alembic import command
    from alembic.config import Config

    from megmis.common.auth import seed_dev_key

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    seed_dev_key(settings)
    # Also run locations/incidents seed
    import scripts.seed as seed_mod

    try:
        seed_mod.seed_locations_and_incidents()
    except Exception:
        # scripts/seed may not be importable as module; invoke functions via path already seeded by CLI
        pass
    yield


@pytest.fixture(scope="session")
def api_keys(settings):
    from megmis.common.auth import seed_dev_key

    seed_dev_key(settings)
    return {
        "a": settings.dev_api_key,
        "b": settings.dev_api_key_b,
    }


@pytest.fixture(scope="session")
def client(api_keys, settings):
    """Single session-scoped client — MCP session manager may only start once."""
    from megmis.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers_a(api_keys):
    return {"X-API-Key": api_keys["a"]}


@pytest.fixture
def headers_b(api_keys):
    return {"X-API-Key": api_keys["b"]}


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs PostGIS + Redis")
    config.addinivalue_line("markers", "bdd: gherkin acceptance")
