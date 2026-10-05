Feature: Google Login
  As a visitor on the AM main app
  I want to start Google OAuth from the login page
  So that federated sign-in is wired (without completing Google credentials)

  @profile:AUTH_GOOGLE_CTA
  Scenario: Google CTA visible on login
    Given I open the main AM app login
    When the login form is ready
    Then I see "Continue with Google"

  @profile:AUTH_GOOGLE_REDIRECT
  Scenario: Click Google redirects to OAuth host
    Given I open the main AM app login
    When I click Continue with Google
    Then the OAuth host is reached or a Google sign-in surface opens
    And I stop without entering Google credentials
