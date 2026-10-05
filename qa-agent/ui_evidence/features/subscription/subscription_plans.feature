Feature: Subscription Plans and Time Left
  As a signed-in user
  I want to see my plan and remaining trial or renewal time
  So that I understand what I am billed for

  @profile:SUB_UI_OPEN
  Scenario: Open subscription page after login
    Given I sign in with valid TEST_USER credentials
    When I open /app/subscription
    Then I see Subscription or Plan chrome

  @profile:SUB_UI_PLANS
  Scenario: Plan cards are visible
    Given I sign in with valid TEST_USER credentials
    When I open /app/subscription
    Then I soft-assert Free or Pro or Upgrade plan copy

  @profile:SUB_UI_TIME_LEFT
  Scenario: Trial or renewal time-left copy
    Given I sign in with valid TEST_USER credentials
    When I open /app/subscription
    Then I soft-assert days left or expires or trial or renew copy
