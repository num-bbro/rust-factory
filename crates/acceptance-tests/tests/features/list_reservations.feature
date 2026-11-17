Feature: List reservations
  So that a customer knows which slots are taken and can find a reservation to cancel, every
  reservation made and not cancelled is listed with its id and time slot, by start time.

  # All scenarios run against one running service, one after another, so the list also holds
  # the reservations of other scenarios: these steps only look at their own reservations. Each
  # scenario uses its own hours of the day, different from those in the other feature files.
  # Times are HH:MM on a single day. An empty list is checked by a unit test in adapters-http.

  Scenario: A reservation appears in the list
    When I reserve 06:00 to 07:00
    Then the list of reservations contains that reservation with 06:00 to 07:00

  Scenario: A cancelled reservation is no longer listed
    Given 07:00 to 08:00 is already reserved
    And I cancel that reservation
    Then the list of reservations does not contain that reservation

  Scenario: Reservations are listed by start time
    Given 16:00 to 17:00 is already reserved
    And 15:00 to 16:00 is already reserved
    Then 15:00 to 16:00 comes before 16:00 to 17:00 in the list
