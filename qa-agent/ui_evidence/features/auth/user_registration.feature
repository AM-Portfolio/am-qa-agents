Feature: User Registration
  As a new visitor on the AM main app
  I want to open registration and see a usable form
  So that I can create an account without breaking prod with junk users

  @profile:AUTH_REG_OPEN
  Scenario: Open register page and see form
    Given I open the register page on the main AM app
    When the Flutter register form is ready
    Then I see "Create your account"
    And I see the Create Account action

  @profile:AUTH_REG_VALIDATION
  Scenario: Empty submit shows validation
    Given I open the register page on the main AM app
    When I click Create Account without filling fields
    Then I see validation feedback for required fields

  @profile:AUTH_REG_FILL
  Scenario: Fill register form with unique email
    Given I open the register page on the main AM app
    When I fill Full name, Email address, Password and Confirm password with a unique qa+ email
    Then the Create Account button remains available
    And I do not submit Create Account (no prod account pollution)
