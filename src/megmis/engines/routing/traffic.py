from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# Seeded corridor congestion profiles for Zimbabwe trunk roads (Gen 2 expansion).
# Extraction seam: this module owns traffic.* and can become a service later (ADR-002).

CORRIDOR_PROFILES: dict[str, dict[str, Any]] = {
    "a1 harare": {"base": 0.55, "peak_hours": (7, 9, 16, 19), "peak_boost": 0.25},
    "a5 harare-bulawayo": {"base": 0.35, "peak_hours": (6, 9, 16, 18), "peak_boost": 0.2},
    "a3 harare-mutare": {"base": 0.25, "peak_hours": (7, 9, 17, 19), "peak_boost": 0.15},
    "bulawayo": {"base": 0.3, "peak_hours": (7, 9, 16, 18), "peak_boost": 0.2},
    "default": {"base": 0.1, "peak_hours": (7, 9, 17, 19), "peak_boost": 0.1},
}


def _match_profile(corridor: str) -> dict[str, Any]:
    key = corridor.strip().lower()
    # Prefer longest/most specific corridor name match
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for name, profile in CORRIDOR_PROFILES.items():
        if name == "default":
            continue
        if name in key or key in name:
            candidates.append((len(name), name, profile))
            continue
        # token overlap only when a highway ref (a1/a3/a5) matches
        tokens = set(name.replace("-", " ").split())
        key_tokens = set(key.replace("-", " ").split())
        refs = {t for t in tokens if t.startswith("a") and t[1:].isdigit()}
        if refs and refs & key_tokens:
            candidates.append((len(name), name, profile))
    if candidates:
        candidates.sort(reverse=True)
        _, name, profile = candidates[0]
        return {**profile, "matched": name}
    return {**CORRIDOR_PROFILES["default"], "matched": "default"}


def get_congestion(corridor: str, at_time: datetime | None = None) -> dict[str, Any]:
    """Traffic sub-module interface (ADR-002)."""
    profile = _match_profile(corridor)
    when = at_time or datetime.now(UTC)
    hour = when.hour
    peaks = profile["peak_hours"]
    in_peak = (peaks[0] <= hour < peaks[1]) or (peaks[2] <= hour < peaks[3])
    congestion = float(profile["base"]) + (float(profile["peak_boost"]) if in_peak else 0.0)
    congestion = min(0.95, congestion)
    return {
        "corridor": corridor,
        "congestion": round(congestion, 3),
        "in_peak": in_peak,
        "matched_profile": profile["matched"],
        "at_time": when.isoformat(),
        "source": "traffic-submodule",
    }


def estimate_time(edge_duration_s: float, at_congestion: float) -> float:
    return edge_duration_s * (1.0 + max(0.0, at_congestion))


def estimate_time_at(
    edge_duration_s: float, corridor: str, at_time: datetime | None = None
) -> dict[str, Any]:
    cong = get_congestion(corridor, at_time)
    duration = estimate_time(edge_duration_s, cong["congestion"])
    return {
        "duration_s": round(duration),
        "base_duration_s": round(edge_duration_s),
        "congestion": cong,
    }


def list_corridors() -> list[str]:
    return [k for k in CORRIDOR_PROFILES if k != "default"]
