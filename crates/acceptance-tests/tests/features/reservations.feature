Feature: Reserve time slots
  So that the front desk never double-books, a time slot can be reserved only once,
  while bookings that merely touch (one ends when the next starts) are fine.

  # All scenarios run against one running service, one after another, so each scenario uses
  # its own hours of the day. Times are HH:MM on a single day.

  Scenario: The service reports that it is healthy
    When I check the service health
    Then the service answers "ok"

  Scenario: Reserve a free slot
    When I reserve 09:00 to 10:00
    Then the reservation is accepted

  Scenario: An overlapping reservation is refused
    Given 11:00 to 12:00 is already reserved
    When I reserve 11:30 to 12:30
    Then the reservation is refused because it overlaps

  Scenario: Back-to-back reservations are both accepted
    Given 13:00 to 14:00 is already reserved
    When I reserve 14:00 to 15:00
    Then the reservation is accepted

  Scenario: A slot that ends before it starts is rejected
    When I reserve 17:00 to 16:00
    Then the reservation is rejected as invalid
