use std::fmt;

/// Minutes in a day; time slots live within one day.
const DAY_MINUTES: u16 = 24 * 60;

/// A half-open time range `[start, end)` within one day, in minutes since midnight.
///
/// Invariant (enforced by [`TimeSlot::new`]): `start < end <= 1440`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TimeSlot {
    start: u16,
    end: u16,
}

impl TimeSlot {
    pub fn new(start: u16, end: u16) -> Result<Self, ScheduleError> {
        if start >= end {
            return Err(ScheduleError::EmptySlot { start, end });
        }
        if end > DAY_MINUTES {
            return Err(ScheduleError::BeyondDay { end });
        }
        Ok(Self { start, end })
    }

    pub fn start(self) -> u16 {
        self.start
    }

    pub fn end(self) -> u16 {
        self.end
    }

    /// Two slots overlap when they share at least one minute. Touching slots (one ends when the
    /// other starts) do not overlap.
    pub fn overlaps(self, other: Self) -> bool {
        self.start < other.end && other.start < self.end
    }
}

/// Identifies a reservation within a schedule.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct ReservationId(u64);

impl ReservationId {
    pub fn new(raw: u64) -> Self {
        Self(raw)
    }

    pub fn get(self) -> u64 {
        self.0
    }
}

impl fmt::Display for ReservationId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ScheduleError {
    #[error("a slot must end after it starts (start {start}, end {end})")]
    EmptySlot { start: u16, end: u16 },
    #[error("a slot must end by midnight (end {end} > {DAY_MINUTES})")]
    BeyondDay { end: u16 },
    #[error("slot overlaps existing reservation {existing}")]
    Overlap { existing: ReservationId },
    #[error("no reservation {0}")]
    NotFound(ReservationId),
}

/// A day's reservations. Invariant: no two reservations overlap.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Schedule {
    reservations: Vec<(ReservationId, TimeSlot)>,
    next_id: u64,
}

impl Schedule {
    pub fn new() -> Self {
        Self::default()
    }

    /// Reserve `slot`, or explain which existing reservation is in the way.
    pub fn book(&mut self, slot: TimeSlot) -> Result<ReservationId, ScheduleError> {
        if let Some((existing, _)) = self.reservations.iter().find(|(_, s)| s.overlaps(slot)) {
            return Err(ScheduleError::Overlap {
                existing: *existing,
            });
        }
        self.next_id += 1;
        let id = ReservationId(self.next_id);
        self.reservations.push((id, slot));
        Ok(id)
    }

    pub fn cancel(&mut self, id: ReservationId) -> Result<TimeSlot, ScheduleError> {
        let pos = self
            .reservations
            .iter()
            .position(|(r, _)| *r == id)
            .ok_or(ScheduleError::NotFound(id))?;
        Ok(self.reservations.remove(pos).1)
    }

    pub fn reservations(&self) -> impl Iterator<Item = (ReservationId, TimeSlot)> + '_ {
        self.reservations.iter().copied()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn slot(start: u16, end: u16) -> TimeSlot {
        TimeSlot::new(start, end).unwrap()
    }

    #[test]
    fn rejects_empty_and_reversed_slots() {
        assert_eq!(
            TimeSlot::new(60, 60),
            Err(ScheduleError::EmptySlot { start: 60, end: 60 })
        );
        assert_eq!(
            TimeSlot::new(90, 60),
            Err(ScheduleError::EmptySlot { start: 90, end: 60 })
        );
    }

    #[test]
    fn rejects_slots_past_midnight() {
        assert_eq!(
            TimeSlot::new(1400, 1441),
            Err(ScheduleError::BeyondDay { end: 1441 })
        );
        assert!(TimeSlot::new(1400, 1440).is_ok());
    }

    #[test]
    fn touching_slots_do_not_overlap() {
        // Both directions: a back-to-back booking must be allowed whichever slot comes first.
        assert!(!slot(60, 120).overlaps(slot(120, 180)));
        assert!(!slot(120, 180).overlaps(slot(60, 120)));
        assert!(slot(60, 121).overlaps(slot(120, 180)));
        assert!(slot(120, 180).overlaps(slot(60, 121)));
    }

    #[test]
    fn back_to_back_bookings_are_accepted() {
        let mut s = Schedule::new();
        s.book(slot(600, 660)).unwrap();
        assert!(
            s.book(slot(540, 600)).is_ok(),
            "ends exactly when the first starts"
        );
        assert!(
            s.book(slot(660, 720)).is_ok(),
            "starts exactly when the first ends"
        );
    }

    #[test]
    fn slot_exposes_its_bounds() {
        let s = slot(540, 600);
        assert_eq!((s.start(), s.end()), (540, 600));
    }

    #[test]
    fn reservation_ids_are_sequential_and_print_as_numbers() {
        let mut s = Schedule::new();
        let first = s.book(slot(0, 10)).unwrap();
        let second = s.book(slot(10, 20)).unwrap();
        assert_eq!((first.get(), second.get()), (1, 2));
        assert_eq!(ReservationId::new(42).to_string(), "42");
    }

    #[test]
    fn booking_an_overlapping_slot_names_the_blocker() {
        let mut s = Schedule::new();
        let first = s.book(slot(540, 600)).unwrap();
        assert_eq!(
            s.book(slot(570, 630)),
            Err(ScheduleError::Overlap { existing: first })
        );
    }

    #[test]
    fn cancelling_frees_the_slot() {
        let mut s = Schedule::new();
        let id = s.book(slot(540, 600)).unwrap();
        assert_eq!(s.cancel(id), Ok(slot(540, 600)));
        assert!(s.book(slot(540, 600)).is_ok());
        assert_eq!(s.cancel(id), Err(ScheduleError::NotFound(id)));
    }

    fn any_slot() -> impl Strategy<Value = TimeSlot> {
        (0..DAY_MINUTES).prop_flat_map(|start| {
            (Just(start), start + 1..=DAY_MINUTES).prop_map(|(s, e)| slot(s, e))
        })
    }

    proptest! {
        /// Overlap is symmetric: if A overlaps B then B overlaps A.
        #[test]
        fn overlap_is_symmetric(a in any_slot(), b in any_slot()) {
            prop_assert_eq!(a.overlaps(b), b.overlaps(a));
        }

        /// Whatever is booked, in any order, the schedule never holds two overlapping slots.
        #[test]
        fn schedule_never_contains_overlaps(slots in prop::collection::vec(any_slot(), 0..40)) {
            let mut s = Schedule::new();
            for slot in slots {
                let _ = s.book(slot);
            }
            let booked: Vec<_> = s.reservations().map(|(_, slot)| slot).collect();
            for (i, a) in booked.iter().enumerate() {
                for b in &booked[i + 1..] {
                    prop_assert!(!a.overlaps(*b), "{a:?} overlaps {b:?}");
                }
            }
        }

        /// A booking is rejected only when it really overlaps something already booked.
        #[test]
        fn rejection_means_real_overlap(slots in prop::collection::vec(any_slot(), 1..40)) {
            let mut s = Schedule::new();
            for slot in slots {
                if let Err(ScheduleError::Overlap { existing }) = s.book(slot) {
                    let (_, blocker) = s.reservations().find(|(id, _)| *id == existing).unwrap();
                    prop_assert!(blocker.overlaps(slot));
                }
            }
        }
    }
}
