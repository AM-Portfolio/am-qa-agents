Feature: User Login
  As a registered user on the AM main app
  I want to sign in with credentials on prod
  So that I reach the authenticated dashboard

  @profile:AUTH_LOGIN_OK
  Scenario: Valid credentials reach dashboard
    Given I open the main AM app login
    When I sign in with valid TEST_USER credentials
    Then I am redirected to /app/dashboard
    And I see Dashboard in the shell

  @profile:AUTH_LOGIN_BAD_PW
  Scenario: Invalid password shows error
    Given I open the main AM app login
    When I sign in with a valid email and a wrong password
    Then I remain on a public auth page
    And I see an authentication error message

  @profile:AUTH_LOGIN_CREDS_ONLY
  Scenario: Demo login path skipped on prod
    Given I open the main AM app login
    When the login form is ready in credentials mode
    Then I see Sign In
    And I do not use Demo Login
