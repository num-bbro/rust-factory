Feature: Cancel a reservation
  So that a customer who cannot come frees the slot for someone else, a reservation can be
  cancelled by its id and its slot can be booked again at once.

  # All scenarios run against one running service, one after another, so each scenario uses
  # its own hours of the day, different from those in reservations.feature. Times are HH:MM on
  # a single day.

  Scenario: Cancel an existing reservation
    Given 18:00 to 19:00 is already reserved
    When I cancel that reservation
    Then the cancellation is accepted

  Scenario: A cancelled slot can be booked again immediately
    Given 20:00 to 21:00 is already reserved
    And I cancel that reservation
    When I reserve 20:00 to 21:00
    Then the reservation is accepted

  Scenario: Cancelling an unknown reservation is refused
    When I cancel reservation 999999
    Then the cancellation is refused as not found

  Scenario: Cancelling the same reservation twice is refused
    Given 22:00 to 23:00 is already reserved
    And I cancel that reservation
    When I cancel that reservation again
    Then the cancellation is refused as not found
