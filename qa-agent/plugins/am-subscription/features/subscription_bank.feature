@skill:happy_flow
@skill:level2_alt_path
Feature: Subscription happy and L2 paths
  Scenario: Plans and me are reachable after prep
    Given data_generator prep on env=dev
    When happy_flow and level2_alt_path run
    Then status is runnable or draft when ungrounded
