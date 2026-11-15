//! Persistence adapter: implements the application's [`ScheduleRepository`] port.
//!
//! This template ships an in-memory store so the whole stack runs with no infrastructure.
//! A project replaces or adds a real database here (decided in an ADR); nothing in `domain` or
//! `application` changes when it does.

use std::sync::{Arc, Mutex};

use application::{RepositoryError, ScheduleRepository};
use domain::Schedule;

/// Thread-safe in-memory schedule store. Cloning shares the same storage.
#[derive(Debug, Clone, Default)]
pub struct InMemoryScheduleRepository {
    schedule: Arc<Mutex<Schedule>>,
}

impl InMemoryScheduleRepository {
    pub fn new() -> Self {
        Self::default()
    }
}

impl ScheduleRepository for InMemoryScheduleRepository {
    /// Holds the lock for the whole update, so concurrent updates run one after another. The
    /// change runs on a copy that replaces the stored schedule only on success; a failing change
    /// leaves the stored schedule as it was, and a panicking one also leaves it intact but
    /// poisons the lock, so every later update is a `RepositoryError` until restart (ADR 0008).
    fn update<T, E, F>(&self, change: F) -> Result<T, E>
    where
        F: FnOnce(&mut Schedule) -> Result<T, E>,
        E: From<RepositoryError>,
    {
        let mut stored = self
            .schedule
            .lock()
            .map_err(|e| RepositoryError(e.to_string()))?;
        let mut copy = stored.clone();
        let value = change(&mut copy)?;
        *stored = copy;
        Ok(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use domain::{ReservationId, TimeSlot};

    fn slot(start: u16, end: u16) -> TimeSlot {
        TimeSlot::new(start, end).unwrap()
    }

    fn snapshot(repo: &InMemoryScheduleRepository) -> Schedule {
        repo.update(|s| Ok::<_, RepositoryError>(s.clone()))
            .unwrap()
    }

    #[test]
    fn successful_change_is_stored_and_shared_between_clones() {
        let repo = InMemoryScheduleRepository::new();
        let id = repo
            .update(|s| {
                s.book(slot(60, 120))
                    .map_err(|e| RepositoryError(e.to_string()))
            })
            .unwrap();
        let stored: Vec<_> = snapshot(&repo.clone()).reservations().collect();
        assert_eq!(stored, vec![(id, slot(60, 120))]);
    }

    #[test]
    fn failing_change_stores_nothing_even_if_it_modified_the_schedule() {
        let repo = InMemoryScheduleRepository::new();
        let err = repo
            .update(|s| -> Result<(), RepositoryError> {
                s.book(slot(60, 120)).unwrap();
                Err(RepositoryError("rule broken".into()))
            })
            .unwrap_err();
        assert_eq!(err.0, "rule broken");
        assert_eq!(snapshot(&repo), Schedule::new());
    }

    #[test]
    fn poisoned_lock_is_a_repository_error_not_a_panic() {
        let repo = InMemoryScheduleRepository::new();
        let poisoner = repo.clone();
        let panicked = std::thread::spawn(move || {
            poisoner.update(|_| -> Result<(), RepositoryError> {
                panic!("change panicked while holding the lock")
            })
        })
        .join();
        assert!(panicked.is_err());
        let err = repo
            .update(|s| {
                s.cancel(ReservationId::new(1))
                    .map_err(|e| RepositoryError(e.to_string()))
            })
            .unwrap_err();
        assert!(err.0.contains("poisoned"), "{err}");
    }
}
