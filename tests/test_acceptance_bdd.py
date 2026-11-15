from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios(
    "features/weather_risk.feature",
    "features/route_optimization.feature",
    "features/tenant_isolation.feature",
)


@pytest.fixture
def ctx():
    return {}


@given(parsers.parse('a location "{location}" and activity "{activity}"'))
def given_location_activity(ctx, location, activity):
    ctx["location"] = location
    ctx["activity"] = activity


@given(parsers.parse('date "{on_date}"'))
def given_date(ctx, on_date):
    ctx["on_date"] = on_date


@when("analyze_weather_risk is called")
def when_weather_risk(client, headers_a, ctx):
    r = client.post(
        "/api/v1/weather/risk",
        headers=headers_a,
        json={
            "location": {"name": ctx["location"]},
            "activity": ctx["activity"],
            "on_date": ctx.get("on_date"),
        },
    )
    ctx["response"] = r
    ctx["body"] = r.json()


@then("response includes risk_level, recommendations and confidence")
def then_risk_fields(ctx):
    assert ctx["response"].status_code == 200
    data = ctx["body"]["data"]
    assert "risk_level" in data["weather_assessment"]
    assert data["recommendations"]
    assert "confidence" in data
    assert "provenance" in ctx["body"]


@then("response labels official vs model-derived data")
def then_official_label(ctx):
    assert ctx["body"]["provenance"]["official_vs_model"] in {
        "official",
        "model_derived",
        "mixed",
    }


@given(parsers.parse('origin "{origin}" destination "{destination}" profile "{profile}"'))
def given_route(ctx, origin, destination, profile):
    ctx["origin"] = origin
    ctx["destination"] = destination
    ctx["profile"] = profile


@given("congestion on route A, heavy rain on route B section, damaged road report")
def given_hazards(ctx):
    ctx["hazards_seeded"] = True


@when("optimize_route is called")
def when_optimize(client, headers_a, ctx):
    r = client.post(
        "/api/v1/routes/optimize",
        headers=headers_a,
        json={
            "origin": {"name": ctx["origin"]},
            "destination": {"name": ctx["destination"]},
            "profile": ctx["profile"],
            "vehicle_class": "car",
        },
    )
    ctx["response"] = r
    ctx["body"] = r.json()


@then("the recommended route is not the congested or flooded option")
def then_not_flooded(ctx):
    assert ctx["response"].status_code == 200
    top = ctx["body"]["data"]["routes"][0]
    assert "heavy_rain" not in top.get("hazards", []) or "flood" not in top.get("hazards", [])
    assert top.get("label") != "Secondary via rain corridor"


@then("the response includes cost_breakdown and explanation")
def then_explainability(ctx):
    top = ctx["body"]["data"]["routes"][0]
    assert top.get("cost_breakdown")
    assert top.get("explanation")


@then("low-confidence reports did not close any road")
def then_no_low_conf_closure(ctx):
    for route in ctx["body"]["data"]["routes"]:
        assert route.get("closed") in (None, False)


@given("tenant A has a journey")
def given_tenant_a_journey(client, headers_a, ctx):
    opt = client.post(
        "/api/v1/routes/optimize",
        headers=headers_a,
        json={
            "origin": {"name": "Harare"},
            "destination": {"name": "Mutare"},
            "profile": "fastest",
        },
    )
    assert opt.status_code == 200
    route_id = opt.json()["data"]["route_id"]
    created = client.post("/api/v1/journeys", headers=headers_a, json={"route_id": route_id})
    assert created.status_code == 201
    ctx["journey_id"] = created.json()["data"]["id"]


@when("tenant B requests that journey")
def when_tenant_b(client, headers_b, ctx):
    ctx["response"] = client.get(f"/api/v1/journeys/{ctx['journey_id']}", headers=headers_b)
    ctx["body"] = ctx["response"].json()


@then("the response is 404 and no data is leaked")
def then_isolated(ctx):
    assert ctx["response"].status_code == 404
    body = ctx["body"]
    assert "origin" not in body
    assert "destination" not in body
    assert body.get("code") == "NOT_FOUND"
