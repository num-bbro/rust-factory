//! Concurrent use of the real in-memory repository through the use cases (bug #26, ADR 0008).
//!
//! Many threads book distinct slots, cancel some of them, and all race for the same contested
//! slots. Timing varies from run to run; the assertions are only about the final state, which
//! must be the same whatever the interleaving.

use std::collections::HashSet;
use std::sync::Barrier;
use std::thread;

use adapters_db::InMemoryScheduleRepository;
use application::{BookSlot, BookingError, CancelReservation, RepositoryError, ScheduleRepository};
use domain::{ReservationId, Schedule, ScheduleError, TimeSlot};

const THREADS: u16 = 16;
/// Own one-minute slots each thread books: minutes `[t * OWN, (t + 1) * OWN)`.
const OWN: u16 = 50;
/// One-minute slots every thread tries to book: minutes `[CONTESTED_FROM, 1440)`.
const CONTESTED_FROM: u16 = 1400;
const ROUNDS: usize = 5;

/// What one thread did.
#[derive(Default)]
struct Outcome {
    /// Own bookings still expected in the schedule.
    kept: Vec<(ReservationId, TimeSlot)>,
    /// Own bookings this thread cancelled successfully.
    cancelled: Vec<ReservationId>,
    /// Contested slots this thread won.
    won: Vec<(ReservationId, TimeSlot)>,
    /// Anything that should not have happened, described.
    unexpected: Vec<String>,
}

fn slot(start: u16) -> TimeSlot {
    TimeSlot::new(start, start + 1).expect("one-minute slot within the day")
}

fn run_thread(repo: &InMemoryScheduleRepository, t: u16, start: &Barrier) -> Outcome {
    let book = BookSlot::new(repo.clone());
    let cancel = CancelReservation::new(repo.clone());
    let mut out = Outcome::default();
    let mut contested = CONTESTED_FROM..1440;
    start.wait();
    for i in 0..OWN {
        let own = slot(t * OWN + i);
        match book.execute(own.start(), own.end()) {
            Ok(id) => out.kept.push((id, own)),
            Err(e) => out
                .unexpected
                .push(format!("booking free {own:?} failed: {e}")),
        }
        // Cancel every second own booking right after making it.
        if i % 2 == 1
            && let Some((id, _)) = out.kept.pop()
        {
            match cancel.execute(id) {
                Ok(()) => out.cancelled.push(id),
                Err(e) => out
                    .unexpected
                    .push(format!("cancelling own {id} failed: {e}")),
            }
        }
        if let Some(minute) = contested.next() {
            let c = slot(minute);
            match book.execute(c.start(), c.end()) {
                Ok(id) => out.won.push((id, c)),
                Err(BookingError::Rule(ScheduleError::Overlap { .. })) => {}
                Err(e) => out.unexpected.push(format!("contested {c:?}: {e}")),
            }
        }
    }
    out
}

/// The stored schedule, read through the port.
fn snapshot(repo: &InMemoryScheduleRepository) -> Schedule {
    repo.read(|s| Ok::<_, RepositoryError>(s.clone()))
        .expect("in-memory storage is available")
}

fn one_round() {
    let repo = InMemoryScheduleRepository::new();
    let start = Barrier::new(usize::from(THREADS));
    let outcomes: Vec<Outcome> = thread::scope(|scope| {
        let handles: Vec<_> = (0..THREADS)
            .map(|t| {
                let (repo, start) = (&repo, &start);
                scope.spawn(move || run_thread(repo, t, start))
            })
            .collect();
        handles
            .into_iter()
            .map(|h| h.join().expect("worker thread did not panic"))
            .collect()
    });

    let unexpected: Vec<_> = outcomes.iter().flat_map(|o| &o.unexpected).collect();
    assert!(unexpected.is_empty(), "unexpected results: {unexpected:#?}");

    // Concurrent bookings of the same slot succeed exactly once.
    let mut won: Vec<_> = outcomes
        .iter()
        .flat_map(|o| o.won.iter().copied())
        .collect();
    won.sort_by_key(|(_, s)| s.start());
    let won_slots: Vec<u16> = won.iter().map(|(_, s)| s.start()).collect();
    assert_eq!(won_slots, (CONTESTED_FROM..1440).collect::<Vec<_>>());

    // Every successful booking got its own id.
    let kept: Vec<_> = outcomes
        .iter()
        .flat_map(|o| o.kept.iter().copied())
        .collect();
    let cancelled: Vec<_> = outcomes
        .iter()
        .flat_map(|o| o.cancelled.iter().copied())
        .collect();
    let all_ids: Vec<_> = kept
        .iter()
        .chain(&won)
        .map(|(id, _)| *id)
        .chain(cancelled.iter().copied())
        .collect();
    let distinct: HashSet<_> = all_ids.iter().collect();
    assert_eq!(distinct.len(), all_ids.len(), "reservation ids were reused");

    // The stored schedule holds exactly the bookings that were kept: none lost, no extra one,
    // and no cancelled reservation came back.
    let mut expected: Vec<_> = kept.into_iter().chain(won).collect();
    expected.sort_by_key(|(id, _)| *id);
    let mut stored: Vec<_> = snapshot(&repo).reservations().collect();
    stored.sort_by_key(|(id, _)| *id);
    assert_eq!(stored, expected);
    assert!(
        cancelled
            .iter()
            .all(|id| stored.iter().all(|(s, _)| s != id)),
        "a cancelled reservation is back"
    );
}

#[test]
fn concurrent_bookings_and_cancellations_are_never_lost_or_duplicated() {
    for _ in 0..ROUNDS {
        one_round();
    }
}
