# Canonical Gen 1 acceptance scenarios.
# Automated via pytest-bdd from tests/features/*.feature (one Feature per file).

Feature: Weather risk
  Scenario: Outdoor wedding risk
    Given a location "Victoria Falls, Zimbabwe" and activity "outdoor_wedding"
    And date "2026-11-20"
    When analyze_weather_risk is called
    Then response includes risk_level, recommendations and confidence
    And response labels official vs model-derived data

# See also: tests/features/route_optimization.feature
# See also: tests/features/tenant_isolation.feature
# Voice agent (Mutare) is Gen 3 — not automated in Gen 1.
