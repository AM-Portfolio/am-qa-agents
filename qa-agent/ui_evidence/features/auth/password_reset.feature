Feature: Password Reset
  As a user who forgot their password
  I want to request a reset and open the reset page
  So that I can recover access

  @profile:AUTH_RESET_PAGE_OPEN
  Scenario: Open reset-password page shell
    Given I open the reset-password page
    When Flutter has loaded
    Then I see reset or password related chrome
    And I soft-assert without requiring a live email token
