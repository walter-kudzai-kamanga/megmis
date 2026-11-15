Feature: Weather risk
  Scenario: Outdoor wedding risk
    Given a location "Victoria Falls, Zimbabwe" and activity "outdoor_wedding"
    And date "2026-11-20"
    When analyze_weather_risk is called
    Then response includes risk_level, recommendations and confidence
    And response labels official vs model-derived data
