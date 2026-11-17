//! HTTP adapter: translates HTTP requests into use-case calls and results into responses.
//!
//! No business rules here — only mapping. Errors from the domain become status codes:
//! invalid input → 422, overlap → 409, unknown reservation → 404, storage failure → 503.
//! See ADR 0007 for the cancel endpoint.

use std::sync::Arc;

use application::{BookSlot, BookingError, CancelReservation, RepositoryError, ScheduleRepository};
use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{delete, get, post},
};
use domain::{ReservationId, Schedule, ScheduleError};
use serde::{Deserialize, Serialize};

/// Build the HTTP API around a repository implementation.
pub fn router<R>(repo: R) -> Router
where
    R: ScheduleRepository + 'static,
{
    Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/reservations", post(book::<R>))
        .route("/reservations/{id}", delete(cancel::<R>))
        .with_state(Arc::new(UseCases::new(repo)))
}

/// A repository shared by several use cases.
struct Shared<R>(Arc<R>);

impl<R> Clone for Shared<R> {
    fn clone(&self) -> Self {
        Self(Arc::clone(&self.0))
    }
}

impl<R: ScheduleRepository> ScheduleRepository for Shared<R> {
    fn update<T, E, F>(&self, change: F) -> Result<T, E>
    where
        F: FnOnce(&mut Schedule) -> Result<T, E>,
        E: From<RepositoryError>,
    {
        self.0.update(change)
    }

    fn read<T, E, F>(&self, look: F) -> Result<T, E>
    where
        F: FnOnce(&Schedule) -> Result<T, E>,
        E: From<RepositoryError>,
    {
        self.0.read(look)
    }
}

struct UseCases<R> {
    book: BookSlot<Shared<R>>,
    cancel: CancelReservation<Shared<R>>,
}

impl<R: ScheduleRepository> UseCases<R> {
    fn new(repo: R) -> Self {
        let shared = Shared(Arc::new(repo));
        Self {
            book: BookSlot::new(shared.clone()),
            cancel: CancelReservation::new(shared),
        }
    }
}

#[derive(Debug, Deserialize)]
struct BookRequest {
    start: u16,
    end: u16,
}

#[derive(Debug, Serialize)]
struct Booked {
    id: u64,
}

#[derive(Debug, Serialize)]
struct Problem {
    error: String,
}

async fn book<R: ScheduleRepository>(
    State(use_cases): State<Arc<UseCases<R>>>,
    Json(req): Json<BookRequest>,
) -> Response {
    match use_cases.book.execute(req.start, req.end) {
        Ok(id) => (StatusCode::CREATED, Json(Booked { id: id.get() })).into_response(),
        Err(err) => problem(&err),
    }
}

async fn cancel<R: ScheduleRepository>(
    State(use_cases): State<Arc<UseCases<R>>>,
    Path(id): Path<u64>,
) -> Response {
    match use_cases.cancel.execute(ReservationId::new(id)) {
        Ok(()) => StatusCode::NO_CONTENT.into_response(),
        Err(err) => problem(&err),
    }
}

fn problem(err: &BookingError) -> Response {
    let status = match err {
        BookingError::Rule(ScheduleError::Overlap { .. }) => StatusCode::CONFLICT,
        BookingError::Rule(ScheduleError::NotFound(_)) => StatusCode::NOT_FOUND,
        BookingError::Rule(_) => StatusCode::UNPROCESSABLE_ENTITY,
        BookingError::Storage(_) => StatusCode::SERVICE_UNAVAILABLE,
    };
    (
        status,
        Json(Problem {
            error: err.to_string(),
        }),
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use application::RepositoryError;
    use axum::body::Body;
    use axum::http::Request;
    use domain::Schedule;
    use http_body_util::BodyExt;
    use std::sync::Mutex;
    use tower::ServiceExt;

    #[derive(Default)]
    struct MemRepo(Mutex<Schedule>);

    impl ScheduleRepository for MemRepo {
        fn update<T, E, F>(&self, change: F) -> Result<T, E>
        where
            F: FnOnce(&mut Schedule) -> Result<T, E>,
            E: From<RepositoryError>,
        {
            let mut stored = self.0.lock().unwrap();
            let mut copy = stored.clone();
            let value = change(&mut copy)?;
            *stored = copy;
            Ok(value)
        }

        fn read<T, E, F>(&self, look: F) -> Result<T, E>
        where
            F: FnOnce(&Schedule) -> Result<T, E>,
            E: From<RepositoryError>,
        {
            look(&self.0.lock().unwrap())
        }
    }

    async fn post(app: &Router, body: &str) -> (StatusCode, serde_json::Value) {
        let req = Request::post("/reservations")
            .header("content-type", "application/json")
            .body(Body::from(body.to_owned()))
            .unwrap();
        let res = app.clone().oneshot(req).await.unwrap();
        let status = res.status();
        let bytes = res.into_body().collect().await.unwrap().to_bytes();
        (status, serde_json::from_slice(&bytes).unwrap())
    }

    struct BrokenRepo;

    impl ScheduleRepository for BrokenRepo {
        fn update<T, E, F>(&self, _: F) -> Result<T, E>
        where
            F: FnOnce(&mut Schedule) -> Result<T, E>,
            E: From<RepositoryError>,
        {
            Err(RepositoryError("disk on fire".into()).into())
        }

        fn read<T, E, F>(&self, _: F) -> Result<T, E>
        where
            F: FnOnce(&Schedule) -> Result<T, E>,
            E: From<RepositoryError>,
        {
            Err(RepositoryError("disk on fire".into()).into())
        }
    }

    #[test]
    fn shared_repository_forwards_reads() {
        let shared = Shared(Arc::new(MemRepo::default()));
        let id = BookSlot::new(shared.clone()).execute(540, 600).unwrap();
        let listed = shared
            .read(|s| Ok::<_, RepositoryError>(s.reservations().collect::<Vec<_>>()))
            .unwrap();
        assert_eq!(listed.len(), 1);
        assert_eq!(listed[0].0, id);
    }

    async fn delete(app: &Router, uri: &str) -> (StatusCode, axum::body::Bytes) {
        let req = Request::delete(uri).body(Body::empty()).unwrap();
        let res = app.clone().oneshot(req).await.unwrap();
        let status = res.status();
        (status, res.into_body().collect().await.unwrap().to_bytes())
    }

    #[tokio::test]
    async fn health_says_ok() {
        let app = router(MemRepo::default());
        let res = app
            .oneshot(Request::get("/health").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn booking_returns_201_then_409_on_overlap() {
        let app = router(MemRepo::default());
        let (status, body) = post(&app, r#"{"start":540,"end":600}"#).await;
        assert_eq!(status, StatusCode::CREATED);
        assert_eq!(body["id"], 1);
        let (status, body) = post(&app, r#"{"start":570,"end":630}"#).await;
        assert_eq!(status, StatusCode::CONFLICT);
        assert!(body["error"].as_str().unwrap().contains("overlaps"));
    }

    #[tokio::test]
    async fn invalid_slot_returns_422() {
        let app = router(MemRepo::default());
        let (status, _) = post(&app, r#"{"start":600,"end":540}"#).await;
        assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);
    }

    #[tokio::test]
    async fn cancel_returns_204_and_frees_the_slot() {
        let app = router(MemRepo::default());
        let (_, body) = post(&app, r#"{"start":540,"end":600}"#).await;
        let uri = format!("/reservations/{}", body["id"]);
        let (status, bytes) = delete(&app, &uri).await;
        assert_eq!(status, StatusCode::NO_CONTENT);
        assert!(bytes.is_empty());
        let (status, _) = post(&app, r#"{"start":540,"end":600}"#).await;
        assert_eq!(status, StatusCode::CREATED);
    }

    #[tokio::test]
    async fn cancel_removes_only_the_given_reservation() {
        let app = router(MemRepo::default());
        post(&app, r#"{"start":540,"end":600}"#).await;
        post(&app, r#"{"start":600,"end":660}"#).await;
        delete(&app, "/reservations/1").await;
        let (status, _) = post(&app, r#"{"start":600,"end":660}"#).await;
        assert_eq!(status, StatusCode::CONFLICT);
    }

    #[tokio::test]
    async fn cancel_unknown_id_returns_404_with_error_body() {
        let app = router(MemRepo::default());
        let (status, bytes) = delete(&app, "/reservations/42").await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        let body: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert!(body["error"].is_string());
    }

    #[tokio::test]
    async fn cancel_twice_returns_404_the_second_time() {
        let app = router(MemRepo::default());
        post(&app, r#"{"start":540,"end":600}"#).await;
        assert_eq!(
            delete(&app, "/reservations/1").await.0,
            StatusCode::NO_CONTENT
        );
        assert_eq!(
            delete(&app, "/reservations/1").await.0,
            StatusCode::NOT_FOUND
        );
    }

    #[tokio::test]
    async fn cancel_storage_failure_returns_503_with_error_body() {
        let app = router(BrokenRepo);
        let (status, bytes) = delete(&app, "/reservations/1").await;
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        let body: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert!(body["error"].is_string());
    }

    #[tokio::test]
    async fn booking_storage_failure_returns_503() {
        let app = router(BrokenRepo);
        let (status, _) = post(&app, r#"{"start":540,"end":600}"#).await;
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    }

    #[tokio::test]
    async fn non_numeric_id_is_rejected_by_the_framework_with_400() {
        let app = router(MemRepo::default());
        let (status, _) = delete(&app, "/reservations/abc").await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
    }
}
