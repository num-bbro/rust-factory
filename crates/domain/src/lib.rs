//! Business rules. **Pure**: no IO, no async, no frameworks, no knowledge of HTTP or databases.
//!
//! Everything here can be tested with plain values, and changing a business rule never requires
//! touching infrastructure code. Other crates depend on this one; it depends on nothing internal.
//!
//! The example rule (replace it with your project's domain): a schedule of time slots in which
//! no two reservations may overlap.

mod schedule;

pub use schedule::{ReservationId, Schedule, ScheduleError, TimeSlot};
