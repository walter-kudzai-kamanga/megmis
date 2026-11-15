"""Gen 4 cost-weight calibration from real trip GPS traces."""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from megmis.engines.routing import cost_model

# In-memory store for non-persistent / test mode
_TRACES: dict[str, dict[str, Any]] = {}
_CALIBRATIONS: dict[str, dict[str, Any]] = {}


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    lat1, lon1 = a
    lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def ingest_trace(
    tenant_id: str,
    *,
    points: list[dict[str, Any]],
    profile: str = "safest",
    route_id: str | None = None,
    meta: dict | None = None,
) -> dict[str, Any]:
    """
    Ingest a GPS polyline. Each point: {lat, lon, ts?} optionally speed_mps.
    Computes distance, duration, mean speed for calibration features.
    """
    if len(points) < 2:
        from megmis.common.errors import AppError

        raise AppError("INVALID_REQUEST", "trace needs >= 2 points", status_code=400)

    dist = 0.0
    for i in range(1, len(points)):
        dist += _haversine_m(
            (float(points[i - 1]["lat"]), float(points[i - 1]["lon"])),
            (float(points[i]["lat"]), float(points[i]["lon"])),
        )
    # duration from timestamps if present else speed hints
    duration_s = 0.0
    if points[0].get("ts") and points[-1].get("ts"):
        t0 = datetime.fromisoformat(str(points[0]["ts"]).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(points[-1]["ts"]).replace("Z", "+00:00"))
        duration_s = max(1.0, (t1 - t0).total_seconds())
    else:
        speeds = [float(p["speed_mps"]) for p in points if p.get("speed_mps")]
        mean_v = sum(speeds) / len(speeds) if speeds else 18.0
        duration_s = dist / max(1.0, mean_v)

    tid = str(uuid4())
    row = {
        "id": tid,
        "tenant_id": tenant_id,
        "profile": profile,
        "route_id": route_id,
        "point_count": len(points),
        "distance_m": round(dist, 1),
        "duration_s": round(duration_s, 1),
        "mean_speed_mps": round(dist / duration_s, 3) if duration_s else 0.0,
        "points": points[:5000],
        "meta": meta or {},
        "created_at": datetime.now(UTC).isoformat(),
    }
    _TRACES[tid] = row

    # optional persistence
    try:
        from megmis.config import get_settings
        from megmis.db import models
        from megmis.db.session import session_scope

        if get_settings().use_persistence:
            from uuid import UUID

            with session_scope(tenant_id=tenant_id) as session:
                session.add(
                    models.GpsTrace(
                        id=UUID(tid),
                        tenant_id=UUID(tenant_id),
                        profile=profile,
                        route_id=UUID(route_id) if route_id else None,
                        distance_m=row["distance_m"],
                        duration_s=row["duration_s"],
                        mean_speed_mps=row["mean_speed_mps"],
                        points=points[:5000],
                        meta=meta or {},
                    )
                )
    except Exception:
        pass
    return row


def calibrate_weights(
    tenant_id: str,
    *,
    profile: str = "safest",
    min_traces: int = 3,
) -> dict[str, Any]:
    """
    Derive adjusted WEIGHT_PROFILES for a profile from ingested traces.

    Heuristic (Gen 4 MVP):
    - Slow mean speeds → increase w_time / congestion sensitivity
    - Long detours vs haversine OD → increase w_dist
    - Persist calibration snapshot; apply into cost_model.WEIGHT_PROFILES[profile]
    """
    traces = [t for t in _TRACES.values() if t["tenant_id"] == tenant_id and t["profile"] == profile]
    # also try DB
    try:
        from uuid import UUID

        from megmis.config import get_settings
        from megmis.db import models
        from megmis.db.session import session_scope

        if get_settings().use_persistence:
            from sqlalchemy import select

            with session_scope(tenant_id=tenant_id) as session:
                rows = session.scalars(
                    select(models.GpsTrace)
                    .where(
                        models.GpsTrace.tenant_id == UUID(tenant_id),
                        models.GpsTrace.profile == profile,
                    )
                    .order_by(models.GpsTrace.created_at.desc())
                    .limit(200)
                ).all()
                for r in rows:
                    traces.append(
                        {
                            "id": str(r.id),
                            "distance_m": r.distance_m,
                            "duration_s": r.duration_s,
                            "mean_speed_mps": r.mean_speed_mps,
                            "points": r.points or [],
                        }
                    )
    except Exception:
        pass

    # dedupe by id
    by_id = {t["id"]: t for t in traces}
    traces = list(by_id.values())
    if len(traces) < min_traces:
        from megmis.common.errors import AppError

        raise AppError(
            "INSUFFICIENT_DATA",
            f"need >= {min_traces} traces for profile={profile}, have {len(traces)}",
            status_code=400,
        )

    mean_speed = sum(t["mean_speed_mps"] for t in traces) / len(traces)
    # straightness: OD haversine / path distance
    ratios = []
    for t in traces:
        pts = t.get("points") or []
        if len(pts) >= 2:
            od = _haversine_m(
                (float(pts[0]["lat"]), float(pts[0]["lon"])),
                (float(pts[-1]["lat"]), float(pts[-1]["lon"])),
            )
            if t["distance_m"] > 0:
                ratios.append(od / t["distance_m"])
    straightness = sum(ratios) / len(ratios) if ratios else 0.75

    base = deepcopy(cost_model.WEIGHT_PROFILES.get(profile, cost_model.WEIGHT_PROFILES["safest"]))
    adjusted = deepcopy(base)
    # slower than ~18 m/s (~65 km/h) → emphasise time
    if mean_speed < 15:
        adjusted["w_time"] = min(1.5, base["w_time"] * 1.25)
    elif mean_speed > 22:
        adjusted["w_time"] = max(0.2, base["w_time"] * 0.9)
    # wiggly paths → distance matters more
    if straightness < 0.7:
        adjusted["w_dist"] = min(1.0, base["w_dist"] * 1.4)
        adjusted["w_surface"] = min(1.0, base.get("w_surface", 0.3) * 1.15)

    # apply globally for this process (tenant-aware overlay stored separately)
    cost_model.WEIGHT_PROFILES[profile] = adjusted

    calib_id = str(uuid4())
    result = {
        "id": calib_id,
        "tenant_id": tenant_id,
        "profile": profile,
        "trace_count": len(traces),
        "features": {
            "mean_speed_mps": round(mean_speed, 3),
            "straightness": round(straightness, 3),
        },
        "weights_before": base,
        "weights_after": adjusted,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _CALIBRATIONS[calib_id] = result

    try:
        from uuid import UUID

        from megmis.config import get_settings
        from megmis.db import models
        from megmis.db.session import session_scope

        if get_settings().use_persistence:
            with session_scope(tenant_id=tenant_id) as session:
                session.add(
                    models.CostCalibration(
                        id=UUID(calib_id),
                        tenant_id=UUID(tenant_id),
                        profile=profile,
                        trace_count=len(traces),
                        weights_before=base,
                        weights_after=adjusted,
                        features=result["features"],
                    )
                )
    except Exception:
        pass
    return result


def list_traces(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = [t for t in _TRACES.values() if t["tenant_id"] == tenant_id]
    rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return rows[:limit]


def current_weights() -> dict[str, dict[str, float]]:
    return deepcopy(cost_model.WEIGHT_PROFILES)
