//! Use cases. Each use case is one thing a user can do, expressed with domain types.
//!
//! The application layer reaches the outside world only through **ports**: traits it defines and
//! adapters implement (e.g. [`ScheduleRepository`]). It never names a concrete database or web
//! framework, so adapters can be swapped and use cases are tested with simple in-memory fakes.

use domain::{ReservationId, Schedule, ScheduleError, TimeSlot};

/// Port: where the schedule is stored. Implemented by an adapter (see `adapters-db`).
pub trait ScheduleRepository: Send + Sync {
    fn load(&self) -> Result<Schedule, RepositoryError>;
    fn save(&self, schedule: &Schedule) -> Result<(), RepositoryError>;
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
        let mut schedule = self.repo.load()?;
        let id = schedule.book(slot)?;
        self.repo.save(&schedule)?;
        Ok(id)
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
        let mut schedule = self.repo.load()?;
        schedule.cancel(id)?;
        self.repo.save(&schedule)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// Test double for the port: keeps the schedule in memory, can be told to fail.
    #[derive(Default)]
    struct FakeRepo {
        schedule: Mutex<Schedule>,
        broken: bool,
        save_broken: bool,
        saves: AtomicUsize,
    }

    impl ScheduleRepository for &FakeRepo {
        fn load(&self) -> Result<Schedule, RepositoryError> {
            if self.broken {
                return Err(RepositoryError("disk on fire".into()));
            }
            Ok(self.schedule.lock().unwrap().clone())
        }
        fn save(&self, schedule: &Schedule) -> Result<(), RepositoryError> {
            if self.save_broken {
                return Err(RepositoryError("disk full".into()));
            }
            self.saves.fetch_add(1, Ordering::SeqCst);
            *self.schedule.lock().unwrap() = schedule.clone();
            Ok(())
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
        assert_eq!(repo.saves.load(Ordering::SeqCst), 0);
    }

    #[test]
    fn cancel_load_failure_is_reported() {
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
    fn cancel_save_failure_is_reported() {
        let repo = FakeRepo::default();
        let id = BookSlot::new(&repo).execute(540, 600).unwrap();
        let failing = FakeRepo {
            schedule: Mutex::new(repo.schedule.lock().unwrap().clone()),
            save_broken: true,
            ..FakeRepo::default()
        };
        let err = CancelReservation::new(&failing).execute(id).unwrap_err();
        assert!(matches!(err, BookingError::Storage(_)));
    }
}
