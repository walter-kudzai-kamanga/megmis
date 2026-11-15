Feature: Tenant isolation
  Scenario: Cross-tenant access denied
    Given tenant A has a journey
    When tenant B requests that journey
    Then the response is 404 and no data is leaked
