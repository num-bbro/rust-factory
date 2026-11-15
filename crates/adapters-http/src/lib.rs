//! HTTP adapter: translates HTTP requests into use-case calls and results into responses.
//!
//! No business rules here — only mapping. Errors from the domain become status codes:
//! invalid input → 422, overlap → 409, storage failure → 503.

use std::sync::Arc;

use application::{BookSlot, BookingError, ScheduleRepository};
use axum::{
    Json, Router,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
};
use domain::ScheduleError;
use serde::{Deserialize, Serialize};

/// Build the HTTP API around a repository implementation.
pub fn router<R>(repo: R) -> Router
where
    R: ScheduleRepository + 'static,
{
    Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/reservations", post(book::<R>))
        .with_state(Arc::new(BookSlot::new(repo)))
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
    State(use_case): State<Arc<BookSlot<R>>>,
    Json(req): Json<BookRequest>,
) -> Response {
    match use_case.execute(req.start, req.end) {
        Ok(id) => (StatusCode::CREATED, Json(Booked { id: id.get() })).into_response(),
        Err(err) => {
            let status = match &err {
                BookingError::Rule(ScheduleError::Overlap { .. }) => StatusCode::CONFLICT,
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
    }
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
        fn load(&self) -> Result<Schedule, RepositoryError> {
            Ok(self.0.lock().unwrap().clone())
        }
        fn save(&self, s: &Schedule) -> Result<(), RepositoryError> {
            *self.0.lock().unwrap() = s.clone();
            Ok(())
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
}
