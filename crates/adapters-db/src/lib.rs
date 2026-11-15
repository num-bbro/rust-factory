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
    fn load(&self) -> Result<Schedule, RepositoryError> {
        self.schedule
            .lock()
            .map(|s| s.clone())
            .map_err(|e| RepositoryError(e.to_string()))
    }

    fn save(&self, schedule: &Schedule) -> Result<(), RepositoryError> {
        let mut guard = self
            .schedule
            .lock()
            .map_err(|e| RepositoryError(e.to_string()))?;
        guard.clone_from(schedule);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use domain::TimeSlot;

    #[test]
    fn saved_schedule_is_loaded_back_and_shared_between_clones() {
        let repo = InMemoryScheduleRepository::new();
        let mut s = repo.load().unwrap();
        s.book(TimeSlot::new(60, 120).unwrap()).unwrap();
        repo.save(&s).unwrap();
        assert_eq!(repo.clone().load().unwrap(), s);
    }
}
