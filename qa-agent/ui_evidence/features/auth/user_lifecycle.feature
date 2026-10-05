Feature: User Lifecycle Registration
  As QA on non-prod
  I want to create a disposable account end-to-end
  So that register → verify → login is proven without polluting prod

  @profile:AUTH_REG_SUBMIT_NONPROD
  @nonprod_only
  Scenario: Submit registration on non-prod with unique qa email
    Given I open the register page on a non-prod AM app
    When I fill Full name, Email, Password and Confirm password with a unique qa+ email
    And I submit Create Account
    Then I see verify-email or success chrome
    And I do not run this scenario against prod
