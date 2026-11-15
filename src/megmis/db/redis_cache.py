from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from megmis.db.session import get_redis

# Plan tiers → requests/minute (token bucket refill rate)
PLAN_LIMITS = {
    "free": 60,
    "pro": 600,
    "enterprise": 6000,
}


def _weather_key(provider: str, lat: float, lon: float, bucket: str) -> str:
    return f"weather:{provider}:{lat:.3f}:{lon:.3f}:{bucket}"


def _route_key(payload: dict[str, Any], profile: str) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"route:{digest}:{profile}"


def cache_get_json(key: str) -> dict[str, Any] | None:
    try:
        raw = get_redis().get(key)
    except Exception:
        return None
    if not raw:
        return None
    return json.loads(raw)


def cache_set_json(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    try:
        get_redis().set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception:
        return


def weather_cache_get(provider: str, lat: float, lon: float) -> dict[str, Any] | None:
    bucket = str(int(time.time() // 600))
    return cache_get_json(_weather_key(provider, lat, lon, bucket))


def weather_cache_set(provider: str, lat: float, lon: float, value: dict[str, Any]) -> None:
    bucket = str(int(time.time() // 600))
    cache_set_json(_weather_key(provider, lat, lon, bucket), value, ttl_seconds=600)


def route_cache_get(payload: dict[str, Any], profile: str) -> dict[str, Any] | None:
    return cache_get_json(_route_key(payload, profile))


def route_cache_set(payload: dict[str, Any], profile: str, value: dict[str, Any]) -> None:
    cache_set_json(_route_key(payload, profile), value, ttl_seconds=300)


def journey_state_set(journey_id: str, state: dict[str, Any]) -> None:
    cache_set_json(f"journey:{journey_id}:state", state, ttl_seconds=86400)


def journey_state_get(journey_id: str) -> dict[str, Any] | None:
    return cache_get_json(f"journey:{journey_id}:state")


def rate_limit_allow(tenant_id: str, *, limit: int = 120, window_seconds: int = 60) -> bool:
    """Legacy fixed-window counter."""
    key = f"ratelimit:{tenant_id}:{window_seconds}:{int(time.time() // window_seconds)}"
    try:
        r = get_redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_seconds)
        return int(count) <= limit
    except Exception:
        return True


def token_bucket_allow(
    tenant_id: str,
    *,
    plan: str = "free",
    cost: int = 1,
    endpoint: str | None = None,
) -> tuple[bool, int]:
    """
    Redis token bucket by plan tier.
    Returns (allowed, retry_after_seconds).
    """
    capacity = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    refill_per_sec = capacity / 60.0
    key = f"ratelimit:bucket:{tenant_id}"
    if endpoint:
        # lighter per-endpoint cap (half plan)
        ep_key = f"ratelimit:bucket:{tenant_id}:{endpoint}"
        ok_ep, retry_ep = _bucket_take(ep_key, capacity=max(10, capacity // 2), refill_per_sec=refill_per_sec / 2, cost=cost)
        if not ok_ep:
            return False, retry_ep
    return _bucket_take(key, capacity=capacity, refill_per_sec=refill_per_sec, cost=cost)


def _bucket_take(key: str, *, capacity: float, refill_per_sec: float, cost: int) -> tuple[bool, int]:
    try:
        r = get_redis()
        now = time.time()
        pipe = r.pipeline()
        pipe.hgetall(key)
        data = pipe.execute()[0] or {}
        tokens = float(data.get("tokens", capacity))
        last = float(data.get("ts", now))
        tokens = min(capacity, tokens + (now - last) * refill_per_sec)
        if tokens < cost:
            need = cost - tokens
            retry = max(1, int(need / refill_per_sec) + 1)
            r.hset(key, mapping={"tokens": tokens, "ts": now})
            r.expire(key, 120)
            return False, retry
        tokens -= cost
        r.hset(key, mapping={"tokens": tokens, "ts": now})
        r.expire(key, 120)
        return True, 0
    except Exception:
        return True, 0
