from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from megmis.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Admin/owner engine — migrations, seed, API-key lookup (bypasses RLS as table owner)."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache
def get_app_engine() -> Engine:
    """
    RLS-enforced app role engine (megmis_app, NOBYPASSRLS).
    Falls back to owner engine when USE_APP_ROLE is off or DATABASE_APP_URL empty.
    """
    settings = get_settings()
    if settings.effective_use_app_role and settings.database_app_url:
        return create_engine(settings.database_app_url, pool_pre_ping=True, future=True)
    return get_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


@lru_cache
def get_app_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_app_engine(), autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope(*, tenant_id: str | None = None, admin: bool = False) -> Iterator[Session]:
    """
    Open a DB session.
    - admin=True or no tenant_id → owner engine (seed/auth/cross-tenant ops)
    - tenant_id set + app role enabled → megmis_app engine with app.tenant_id GUC
    """
    settings = get_settings()
    use_app = (
        not admin
        and tenant_id is not None
        and settings.effective_use_app_role
        and bool(settings.database_app_url)
    )
    factory = get_app_session_factory() if use_app else get_session_factory()
    session = factory()
    try:
        if tenant_id:
            session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


def reset_db_caches() -> None:
    get_engine.cache_clear()
    get_app_engine.cache_clear()
    get_session_factory.cache_clear()
    get_app_session_factory.cache_clear()
    get_redis.cache_clear()
