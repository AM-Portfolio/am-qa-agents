Feature: User Sessions and Logout
  As a signed-in user
  I want to see active sessions and sign out
  So that I can secure my account on this device and others

  @profile:AUTH_SESSIONS_LIST_UI
  Scenario: Profile shows session / security chrome after login
    Given I sign in with valid TEST_USER credentials
    When I open the profile area
    Then I see account or security related chrome
    And I capture a screenshot of the sessions surface

  @profile:AUTH_LOGOUT_UI
  Scenario: Sign out returns to public login
    Given I sign in with valid TEST_USER credentials
    When I open the account menu and choose Sign out
    Then I am on a public auth page
    And I see Sign In
