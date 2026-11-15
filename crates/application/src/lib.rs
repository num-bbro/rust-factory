//! Use cases. Each use case is one thing a user can do, expressed with domain types.
//!
//! The application layer reaches the outside world only through **ports**: traits it defines and
//! adapters implement (e.g. [`ScheduleRepository`]). It never names a concrete database or web
//! framework, so adapters can be swapped and use cases are tested with simple in-memory fakes.

use domain::{ReservationId, Schedule, ScheduleError, TimeSlot};

/// Port: where the schedule is stored. Implemented by an adapter (see `adapters-db`).
///
/// Every change goes through [`update`](Self::update), which reads, changes and stores the
/// schedule as **one atomic step**, so concurrent changes never overwrite each other (ADR 0008).
pub trait ScheduleRepository: Send + Sync {
    /// Run `change` on the current schedule and store the result, atomically: no other change
    /// can happen between reading the schedule and storing it.
    ///
    /// - `change` returns `Ok(value)`: the changed schedule is stored and `Ok(value)` returned.
    /// - `change` returns `Err(e)`: nothing is stored (even if `change` modified the schedule
    ///   before failing) and `Err(e)` is returned.
    /// - Storage fails: the [`RepositoryError`] is returned as `E`; `change` may not have run.
    fn update<T, E, F>(&self, change: F) -> Result<T, E>
    where
        F: FnOnce(&mut Schedule) -> Result<T, E>,
        E: From<RepositoryError>;
}

/// A storage failure, described without leaking the storage technology.
#[derive(Debug, thiserror::Error)]
#[error("storage unavailable: {0}")]
pub struct RepositoryError(pub String);

#[derive(Debug, thiserror::Error)]
pub enum BookingError {
    #[error(transparent)]
    Rule(#[from] ScheduleError),
    #[error(transparent)]
    Storage(#[from] RepositoryError),
}

/// Use case: reserve a time slot.
#[derive(Debug)]
pub struct BookSlot<R> {
    repo: R,
}

impl<R: ScheduleRepository> BookSlot<R> {
    pub fn new(repo: R) -> Self {
        Self { repo }
    }

    pub fn execute(&self, start: u16, end: u16) -> Result<ReservationId, BookingError> {
        let slot = TimeSlot::new(start, end)?;
        self.repo
            .update(|schedule| schedule.book(slot).map_err(BookingError::from))
    }
}

/// Use case: cancel a reservation by its id, freeing its slot at once.
#[derive(Debug)]
pub struct CancelReservation<R> {
    repo: R,
}

impl<R: ScheduleRepository> CancelReservation<R> {
    pub fn new(repo: R) -> Self {
        Self { repo }
    }

    pub fn execute(&self, id: ReservationId) -> Result<(), BookingError> {
        self.repo.update(|schedule| {
            schedule.cancel(id)?;
            Ok(())
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// Test double for the port: keeps the schedule in memory, can be told to fail, counts
    /// the changes it stores.
    #[derive(Default)]
    struct FakeRepo {
        schedule: Mutex<Schedule>,
        /// Storage unavailable: fails before the change runs.
        broken: bool,
        /// Storing fails after the change ran.
        store_broken: bool,
        commits: AtomicUsize,
    }

    impl ScheduleRepository for &FakeRepo {
        fn update<T, E, F>(&self, change: F) -> Result<T, E>
        where
            F: FnOnce(&mut Schedule) -> Result<T, E>,
            E: From<RepositoryError>,
        {
            if self.broken {
                return Err(RepositoryError("disk on fire".into()).into());
            }
            let mut stored = self.schedule.lock().unwrap();
            let mut copy = stored.clone();
            let value = change(&mut copy)?;
            if self.store_broken {
                return Err(RepositoryError("disk full".into()).into());
            }
            *stored = copy;
            self.commits.fetch_add(1, Ordering::SeqCst);
            Ok(value)
        }
    }

    #[test]
    fn books_and_persists() {
        let repo = FakeRepo::default();
        let id = BookSlot::new(&repo).execute(540, 600).unwrap();
        let saved: Vec<_> = repo.schedule.lock().unwrap().reservations().collect();
        assert_eq!(saved, vec![(id, TimeSlot::new(540, 600).unwrap())]);
    }

    #[test]
    fn overlap_is_a_rule_error_and_nothing_is_saved() {
        let repo = FakeRepo::default();
        let book = BookSlot::new(&repo);
        book.execute(540, 600).unwrap();
        let err = book.execute(570, 630).unwrap_err();
        assert!(matches!(
            err,
            BookingError::Rule(ScheduleError::Overlap { .. })
        ));
        assert_eq!(repo.schedule.lock().unwrap().reservations().count(), 1);
        assert_eq!(repo.commits.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn invalid_slot_never_touches_storage() {
        let repo = FakeRepo {
            broken: true,
            ..FakeRepo::default()
        };
        let err = BookSlot::new(&repo).execute(600, 540).unwrap_err();
        assert!(matches!(
            err,
            BookingError::Rule(ScheduleError::EmptySlot { .. })
        ));
    }

    #[test]
    fn storage_failure_is_reported() {
        let repo = FakeRepo {
            broken: true,
            ..FakeRepo::default()
        };
        let err = BookSlot::new(&repo).execute(540, 600).unwrap_err();
        assert!(matches!(err, BookingError::Storage(_)));
    }

    #[test]
    fn cancelled_slot_can_be_booked_again() {
        let repo = FakeRepo::default();
        let book = BookSlot::new(&repo);
        let id = book.execute(540, 600).unwrap();
        CancelReservation::new(&repo).execute(id).unwrap();
        assert_eq!(repo.schedule.lock().unwrap().reservations().count(), 0);
        book.execute(540, 600).unwrap();
    }

    #[test]
    fn cancel_removes_only_the_given_reservation() {
        let repo = FakeRepo::default();
        let book = BookSlot::new(&repo);
        let first = book.execute(540, 600).unwrap();
        let second = book.execute(600, 660).unwrap();
        CancelReservation::new(&repo).execute(first).unwrap();
        let saved: Vec<_> = repo.schedule.lock().unwrap().reservations().collect();
        assert_eq!(saved, vec![(second, TimeSlot::new(600, 660).unwrap())]);
    }

    #[test]
    fn cancel_unknown_id_is_a_rule_error_and_nothing_is_saved() {
        let repo = FakeRepo::default();
        let err = CancelReservation::new(&repo)
            .execute(ReservationId::new(42))
            .unwrap_err();
        assert!(matches!(
            err,
            BookingError::Rule(ScheduleError::NotFound(_))
        ));
        assert_eq!(repo.commits.load(Ordering::SeqCst), 0);
    }

    #[test]
    fn cancel_storage_unavailable_is_reported() {
        let repo = FakeRepo {
            broken: true,
            ..FakeRepo::default()
        };
        let err = CancelReservation::new(&repo)
            .execute(ReservationId::new(1))
            .unwrap_err();
        assert!(matches!(err, BookingError::Storage(_)));
    }

    #[test]
    fn cancel_store_failure_is_reported() {
        let repo = FakeRepo::default();
        let id = BookSlot::new(&repo).execute(540, 600).unwrap();
        let failing = FakeRepo {
            schedule: Mutex::new(repo.schedule.lock().unwrap().clone()),
            store_broken: true,
            ..FakeRepo::default()
        };
        let err = CancelReservation::new(&failing).execute(id).unwrap_err();
        assert!(matches!(err, BookingError::Storage(_)));
        assert_eq!(failing.schedule.lock().unwrap().reservations().count(), 1);
    }

    #[test]
    fn booking_store_failure_is_reported_and_nothing_is_kept() {
        let repo = FakeRepo {
            store_broken: true,
            ..FakeRepo::default()
        };
        let err = BookSlot::new(&repo).execute(540, 600).unwrap_err();
        assert!(matches!(err, BookingError::Storage(_)));
        assert_eq!(repo.schedule.lock().unwrap().reservations().count(), 0);
    }
}
