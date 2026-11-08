@skill:happy_flow
Feature: Identity login seed
  Scenario: Login JWT for SPT
    Given SPT auth env names set
    When identity prep runs on env=dev
    Then login step is PASSED or fail-closed
