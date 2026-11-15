Feature: Route optimization (Harare -> Bulawayo)
  Scenario: Avoid congestion, rain and damaged road
    Given origin "Harare" destination "Bulawayo" profile "safest"
    And congestion on route A, heavy rain on route B section, damaged road report
    When optimize_route is called
    Then the recommended route is not the congested or flooded option
    And the response includes cost_breakdown and explanation
    And low-confidence reports did not close any road
