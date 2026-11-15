from __future__ import annotations

import math
from typing import Any

WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "fastest": {"w_time": 1.0, "w_dist": 0.05, "w_surface": 0.1, "w_weather": 0.1, "w_incident": 0.2},
    "safest": {"w_time": 0.4, "w_dist": 0.05, "w_surface": 0.6, "w_weather": 0.8, "w_incident": 0.9},
    "cheapest": {"w_time": 0.5, "w_dist": 0.5, "w_surface": 0.2, "w_weather": 0.2, "w_incident": 0.3},
    "fuel": {"w_time": 0.3, "w_dist": 0.6, "w_surface": 0.4, "w_weather": 0.2, "w_incident": 0.2},
}

BASE_SURFACE = {"paved": 0.0, "rough": 0.3, "unpaved": 0.6}
VEHICLE_FACTOR = {"car": 1.0, "light_truck": 1.2, "hgv": 1.5}


def surface_penalty(segment: dict[str, Any], vehicle_class: str) -> float:
    base = BASE_SURFACE.get(segment.get("surface", "paved"), 0.3)
    for inc in segment.get("incidents") or []:
        if inc.get("type") == "pothole":
            conf = float(inc.get("confidence") or 0)
            base += 0.2 * conf
    return min(1.0, base * VEHICLE_FACTOR.get(vehicle_class, 1.0))


def weather_penalty(segment: dict[str, Any]) -> float:
    score = 0.0
    weather = segment.get("weather")
    if weather == "heavy_rain":
        score = max(score, 0.8)
    if float(segment.get("flood_exposure") or 0) >= 0.5:
        score = max(score, min(1.0, float(segment["flood_exposure"])))
    if float(segment.get("visibility_km") or 20) < 5:
        score = max(score, 0.5)
    if float(segment.get("wind_ms") or 0) >= 10:
        score = max(score, 0.4)
    return min(1.0, score)


def incident_penalty(segment: dict[str, Any]) -> tuple[float, bool]:
    """Returns (penalty, is_hard_closure). Low-confidence never closes a road."""
    total = 0.0
    hard_closure = False
    for inc in segment.get("incidents") or []:
        conf = float(inc.get("confidence") or 0)
        severity_norm = float(inc.get("severity") or 1) / 5.0
        age = float(inc.get("age_hours") or 0)
        decay = math.exp(-age / 24.0)
        contrib = severity_norm * conf * decay
        if conf < 0.3:
            contrib = min(contrib, 0.1)
        else:
            if inc.get("verified_closure"):
                hard_closure = True
        total += contrib
    return min(1.0, total), hard_closure


def score_candidate(
    candidate: dict[str, Any],
    profile: str,
    vehicle_class: str,
) -> dict[str, Any]:
    weights = WEIGHT_PROFILES.get(profile, WEIGHT_PROFILES["safest"])
    # Normalise time/distance against rough Zimbabwe intercity scales
    time_norm = float(candidate["duration_s"]) / 3600.0 / 8.0  # ~8h scale
    dist_norm = float(candidate["distance_m"]) / 1000.0 / 500.0  # ~500km scale

    surf = 0.0
    weather = 0.0
    incident = 0.0
    closed = False
    hazards: list[str] = []

    for seg in candidate.get("segments") or []:
        surf = max(surf, surface_penalty(seg, vehicle_class))
        weather = max(weather, weather_penalty(seg))
        ip, hard = incident_penalty(seg)
        incident = max(incident, ip)
        if hard:
            closed = True
        if seg.get("weather") == "heavy_rain":
            hazards.append("heavy_rain")
        if float(seg.get("congestion") or 0) >= 0.5:
            hazards.append("congestion")
        for inc in seg.get("incidents") or []:
            hazards.append(str(inc.get("type")))

    if closed:
        total = float("inf")
    else:
        # Congestion soft-cost folded into time for Gen 1
        congestion = max(float(s.get("congestion") or 0) for s in (candidate.get("segments") or [{}]))
        time_term = time_norm * (1.0 + congestion)
        total = (
            weights["w_time"] * time_term
            + weights["w_dist"] * dist_norm
            + weights["w_surface"] * surf
            + weights["w_weather"] * weather
            + weights["w_incident"] * incident
        )

    breakdown = [
        {"term": "time", "value": round(time_norm, 4), "weight": weights["w_time"], "contribution": round(weights["w_time"] * time_norm, 4)},
        {"term": "distance", "value": round(dist_norm, 4), "weight": weights["w_dist"], "contribution": round(weights["w_dist"] * dist_norm, 4)},
        {"term": "surface", "value": round(surf, 4), "weight": weights["w_surface"], "contribution": round(weights["w_surface"] * surf, 4)},
        {"term": "weather", "value": round(weather, 4), "weight": weights["w_weather"], "contribution": round(weights["w_weather"] * weather, 4)},
        {"term": "incident", "value": round(incident, 4), "weight": weights["w_incident"], "contribution": round(weights["w_incident"] * incident, 4)},
    ]

    reasons = []
    if "congestion" in hazards:
        reasons.append("avoids congested primary corridor" if profile != "fastest" else "uses primary corridor despite congestion")
    if "heavy_rain" in hazards or "flood" in hazards:
        reasons.append("penalises rain/flood exposure")
    if "damaged_road" in hazards or "pothole" in hazards:
        reasons.append("accounts for road-surface reports (low-confidence never closes roads)")
    if not reasons:
        reasons.append("balanced time and distance")

    explanation = (
        f"{candidate.get('label', candidate.get('id'))}: cost={total if total != float('inf') else 'CLOSED'} "
        f"via {', '.join(reasons)}."
    )

    out = {
        "id": candidate.get("id"),
        "label": candidate.get("label"),
        "distance_m": round(float(candidate["distance_m"])),
        "duration_s": round(float(candidate["duration_s"])),
        "hazards": sorted(set(hazards)),
        "cost": None if total == float("inf") else round(total, 4),
        "closed": closed,
        "cost_breakdown": breakdown,
        "explanation": explanation,
        "algorithm": candidate.get("algorithm") or "cost-model",
    }
    if candidate.get("geometry"):
        out["geometry"] = candidate["geometry"]
    if candidate.get("node_path"):
        out["node_path"] = candidate["node_path"]
    if candidate.get("via"):
        out["via"] = candidate["via"]
    return out
