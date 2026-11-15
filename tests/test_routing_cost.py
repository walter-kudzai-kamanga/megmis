from megmis.engines.routing.cost_model import score_candidate


def _candidate(congestion: float, weather: str, incidents: list) -> dict:
    return {
        "id": "t",
        "label": "test",
        "distance_m": 400_000,
        "duration_s": 20_000,
        "segments": [
            {
                "surface": "paved",
                "weather": weather,
                "flood_exposure": 0.7 if weather == "heavy_rain" else 0.0,
                "visibility_km": 3.0 if weather == "heavy_rain" else 12.0,
                "wind_ms": 4.0,
                "congestion": congestion,
                "incidents": incidents,
            }
        ],
    }


def test_safest_prefers_non_flooded_route():
    congested = score_candidate(_candidate(0.55, "clear", []), "safest", "car")
    flooded = score_candidate(
        _candidate(
            0.1,
            "heavy_rain",
            [{"type": "flood", "severity": 4, "confidence": 0.85, "age_hours": 2, "verified_closure": False}],
        ),
        "safest",
        "car",
    )
    assert congested["cost"] is not None
    assert flooded["cost"] is not None
    assert congested["cost"] < flooded["cost"]
    assert "cost_breakdown" in congested
    assert congested["explanation"]


def test_low_confidence_never_closes_road():
    scored = score_candidate(
        _candidate(
            0.0,
            "clear",
            [{"type": "pothole", "severity": 5, "confidence": 0.2, "age_hours": 1, "verified_closure": True}],
        ),
        "safest",
        "car",
    )
    assert scored["closed"] is False
    assert scored["cost"] is not None
