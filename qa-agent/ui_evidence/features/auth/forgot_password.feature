Feature: Forgot Password
  As a user who cannot sign in
  I want to request a password reset email
  So that I can recover access

  @profile:AUTH_FORGOT_OPEN
  Scenario: Open forgot-password page
    Given I open the forgot-password page
    When the Flutter form is ready
    Then I see "Forgot password?"
    And I see Send Reset Link

  @profile:AUTH_FORGOT_SUBMIT
  Scenario: Submit known email shows confirmation UI
    Given I open the forgot-password page
    When I enter the known TEST_USER email and click Send Reset Link
    Then I see a confirmation or success message about reset instructions
