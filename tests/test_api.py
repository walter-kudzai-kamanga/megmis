def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_weather_risk_outdoor_wedding(client, headers_a):
    r = client.post(
        "/api/v1/weather/risk",
        headers=headers_a,
        json={
            "location": {"name": "Victoria Falls, Zimbabwe"},
            "activity": "outdoor_wedding",
            "on_date": "2026-11-20",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "weather_assessment" in body["data"]
    assert "recommendations" in body["data"]
    assert "provenance" in body
    assert "official_vs_model" in body["provenance"]


def test_optimize_harare_bulawayo(client, headers_a):
    r = client.post(
        "/api/v1/routes/optimize",
        headers=headers_a,
        json={
            "origin": {"name": "Harare"},
            "destination": {"name": "Bulawayo"},
            "profile": "safest",
            "vehicle_class": "car",
        },
    )
    assert r.status_code == 200
    body = r.json()
    routes = body["data"]["routes"]
    assert routes
    top = routes[0]
    assert "cost_breakdown" in top
    assert "explanation" in top
    assert top.get("label") != "Secondary via rain corridor"
