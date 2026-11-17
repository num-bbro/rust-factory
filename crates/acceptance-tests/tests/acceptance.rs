//! Step definitions for `features/*.feature`, executed over HTTP against `ACCEPTANCE_BASE_URL`.

use std::time::Duration;

use cucumber::{World, given, then, when};
use serde_json::{Value, json};

#[derive(Debug, World)]
#[world(init = Self::new)]
struct Api {
    base: String,
    client: reqwest::Client,
    status: u16,
    body: Value,
    /// Id returned by the last successful `POST /reservations`.
    reservation_id: Option<u64>,
}

impl Api {
    fn new() -> Self {
        Self {
            base: base_url().unwrap_or_default(),
            client: reqwest::Client::new(),
            status: 0,
            body: Value::Null,
            reservation_id: None,
        }
    }

    async fn reserve(&mut self, from: &str, to: &str) {
        let res = self
            .client
            .post(format!("{}/reservations", self.base))
            .json(&json!({ "start": minutes(from), "end": minutes(to) }))
            .send()
            .await
            .expect("service reachable");
        self.status = res.status().as_u16();
        self.body = res.json().await.unwrap_or(Value::Null);
        self.reservation_id = self.body["id"].as_u64();
    }

    async fn cancel(&mut self, id: u64) {
        let res = self
            .client
            .delete(format!("{}/reservations/{id}", self.base))
            .send()
            .await
            .expect("service reachable");
        self.status = res.status().as_u16();
        self.body = res.json().await.unwrap_or(Value::Null);
    }

    /// `GET /reservations`: the listed reservations, in the order the service gives them. The
    /// list also holds other scenarios' reservations (one shared service).
    async fn list(&mut self) -> Vec<Value> {
        let res = self
            .client
            .get(format!("{}/reservations", self.base))
            .send()
            .await
            .expect("service reachable");
        self.status = res.status().as_u16();
        self.body = res.json().await.unwrap_or(Value::Null);
        assert_eq!(self.status, 200, "body: {}", self.body);
        self.body["reservations"]
            .as_array()
            .unwrap_or_else(|| panic!("a list of reservations: {}", self.body))
            .clone()
    }
}

/// Position in `listed` of the reservation for `from`..`to`. Reservations never overlap, so at
/// most one has that slot.
fn position_of(listed: &[Value], from: &str, to: &str) -> usize {
    let (start, end) = (minutes(from), minutes(to));
    listed
        .iter()
        .position(|r| r["start"] == start && r["end"] == end)
        .unwrap_or_else(|| panic!("{from} to {to} is listed: {listed:?}"))
}

/// "09:30" -> 570 minutes since midnight.
fn minutes(hhmm: &str) -> u16 {
    let (h, m) = hhmm.split_once(':').expect("time as HH:MM");
    h.parse::<u16>().expect("hours") * 60 + m.parse::<u16>().expect("minutes")
}

fn base_url() -> Option<String> {
    std::env::var("ACCEPTANCE_BASE_URL")
        .ok()
        .map(|u| u.trim_end_matches('/').to_owned())
}

#[when("I check the service health")]
async fn check_health(api: &mut Api) {
    let res = api
        .client
        .get(format!("{}/health", api.base))
        .send()
        .await
        .expect("service reachable");
    api.status = res.status().as_u16();
    api.body = Value::String(res.text().await.unwrap_or_default());
}

#[then(expr = "the service answers {string}")]
fn service_answers(api: &mut Api, expected: String) {
    assert_eq!(api.status, 200);
    assert_eq!(api.body, Value::String(expected));
}

#[given(expr = "{word} to {word} is already reserved")]
async fn already_reserved(api: &mut Api, from: String, to: String) {
    api.reserve(&from, &to).await;
    assert_eq!(api.status, 201, "setup booking failed: {}", api.body);
}

#[when(expr = "I reserve {word} to {word}")]
async fn reserve(api: &mut Api, from: String, to: String) {
    api.reserve(&from, &to).await;
}

#[given("I cancel that reservation")]
#[when("I cancel that reservation")]
async fn cancel(api: &mut Api) {
    let id = api.reservation_id.expect("a reservation was made earlier");
    api.cancel(id).await;
}

#[when(expr = "I cancel reservation {int}")]
async fn cancel_by_id(api: &mut Api, id: u64) {
    api.cancel(id).await;
}

#[when("I cancel that reservation again")]
async fn cancel_again(api: &mut Api) {
    let id = api.reservation_id.expect("a reservation was made earlier");
    api.cancel(id).await;
}

#[then("the cancellation is refused as not found")]
fn cancellation_refused_not_found(api: &mut Api) {
    assert_eq!(api.status, 404, "body: {}", api.body);
    assert!(
        api.body["error"].as_str().is_some(),
        "an error is returned: {}",
        api.body
    );
}

#[then("the cancellation is accepted")]
fn cancellation_accepted(api: &mut Api) {
    assert_eq!(api.status, 204, "body: {}", api.body);
}

#[then("the reservation is accepted")]
fn accepted(api: &mut Api) {
    assert_eq!(api.status, 201, "body: {}", api.body);
    assert!(
        api.body["id"].as_u64().is_some(),
        "an id is returned: {}",
        api.body
    );
}

#[then("the reservation is refused because it overlaps")]
fn refused_overlap(api: &mut Api) {
    assert_eq!(api.status, 409, "body: {}", api.body);
    let error = api.body["error"].as_str().unwrap_or_default();
    assert!(
        error.contains("overlaps"),
        "error explains the overlap: {error}"
    );
}

#[then(expr = "the list of reservations contains that reservation with {word} to {word}")]
async fn listed_with_slot(api: &mut Api, from: String, to: String) {
    let id = api.reservation_id.expect("a reservation was made earlier");
    let listed = api.list().await;
    let mine: Vec<&Value> = listed.iter().filter(|r| r["id"] == id).collect();
    assert_eq!(
        mine,
        [&json!({ "id": id, "start": minutes(&from), "end": minutes(&to) })],
        "reservation {id} is listed once with its slot: {listed:?}"
    );
}

#[then("the list of reservations does not contain that reservation")]
async fn not_listed(api: &mut Api) {
    let id = api.reservation_id.expect("a reservation was made earlier");
    let listed = api.list().await;
    assert!(
        listed.iter().all(|r| r["id"] != id),
        "reservation {id} is not listed: {listed:?}"
    );
}

#[then(expr = "{word} to {word} comes before {word} to {word} in the list")]
async fn listed_before(api: &mut Api, from: String, to: String, from2: String, to2: String) {
    let listed = api.list().await;
    let (first, second) = (
        position_of(&listed, &from, &to),
        position_of(&listed, &from2, &to2),
    );
    assert!(
        first < second,
        "{from} to {to} comes before {from2} to {to2}: {listed:?}"
    );
}

#[then("the reservation is rejected as invalid")]
fn rejected_invalid(api: &mut Api) {
    assert_eq!(api.status, 422, "body: {}", api.body);
}

/// The container may still be starting; wait until /health answers (at most ~15 s).
async fn wait_until_healthy(base: &str) {
    let client = reqwest::Client::new();
    for _ in 0..30 {
        if let Ok(res) = client.get(format!("{base}/health")).send().await
            && res.status().is_success()
        {
            return;
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    panic!("service at {base} did not become healthy");
}

#[tokio::main]
async fn main() {
    let Some(base) = base_url() else {
        // Run via `just acceptance` or CI. Plain `cargo test` (e.g. inside cargo-mutants) skips,
        // unless ACCEPTANCE_REQUIRED is set, as it is in CI, where skipping must fail loudly.
        if std::env::var_os("ACCEPTANCE_REQUIRED").is_some() {
            eprintln!("ACCEPTANCE_BASE_URL is not set but acceptance tests are required");
            std::process::exit(1);
        }
        eprintln!("acceptance tests skipped: ACCEPTANCE_BASE_URL not set (use `just acceptance`)");
        return;
    };
    wait_until_healthy(&base).await;
    Api::cucumber()
        .max_concurrent_scenarios(1) // scenarios share one running service
        .fail_on_skipped()
        .run_and_exit(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/features"))
        .await;
}
