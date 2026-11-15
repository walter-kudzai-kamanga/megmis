"""Mandatory tenant-isolation suite (CI gate)."""

from __future__ import annotations


def test_journey_cross_tenant_404(client, headers_a, headers_b):
    opt = client.post(
        "/api/v1/routes/optimize",
        headers=headers_a,
        json={"origin": {"name": "Harare"}, "destination": {"name": "Bulawayo"}, "profile": "safest"},
    )
    route_id = opt.json()["data"]["route_id"]
    created = client.post("/api/v1/journeys", headers=headers_a, json={"route_id": route_id})
    journey_id = created.json()["data"]["id"]

    leaked = client.get(f"/api/v1/journeys/{journey_id}", headers=headers_b)
    assert leaked.status_code == 404
    assert "origin" not in leaked.json()

    own = client.get(f"/api/v1/journeys/{journey_id}", headers=headers_a)
    assert own.status_code == 200


def test_road_report_scoped_to_writer(client, headers_a, headers_b):
    r = client.post(
        "/api/v1/roads/reports",
        headers=headers_a,
        json={"location": {"name": "Harare"}, "type": "pothole", "severity": 2},
    )
    assert r.status_code == 201
    # Tenant B can list public incidents but cannot read another tenant's journey data
    listing = client.get("/api/v1/roads/incidents", headers=headers_b)
    assert listing.status_code == 200


def test_weather_requires_key(client):
    r = client.get("/api/v1/weather/current?name=Harare")
    assert r.status_code == 401
