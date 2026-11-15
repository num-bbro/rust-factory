//! The binary: chooses adapters, wires them into the use cases, and serves HTTP.
//!
//! Configuration comes from the environment (12-factor):
//!   `PORT`      listen port (default 8080)
//!   `RUST_LOG`  log filter (default "info")
//!
//! `app healthcheck` asks the running server on `PORT` for `/health` and exits 0 if it answers
//! 200. The container image has no shell or curl, so its health check uses this.
//!
//! This file is startup wiring: it is covered by the acceptance tests against the running
//! container, not by unit tests (excluded from coverage and mutation testing).

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::process::ExitCode;
use std::time::Duration;

use adapters_db::InMemoryScheduleRepository;
use tracing_subscriber::EnvFilter;

fn main() -> ExitCode {
    if std::env::args().nth(1).as_deref() == Some("healthcheck") {
        return healthcheck(port());
    }
    match serve() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("fatal: {e}");
            ExitCode::FAILURE
        }
    }
}

fn port() -> u16 {
    std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8080)
}

#[tokio::main]
async fn serve() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let addr = SocketAddr::from(([0, 0, 0, 0], port()));
    let app = adapters_http::router(InMemoryScheduleRepository::new());
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(%addr, version = env!("CARGO_PKG_VERSION"), "listening");

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    tracing::info!("stopped");
    Ok(())
}

/// Minimal HTTP/1.1 probe of `/health` on localhost, standard library only.
fn healthcheck(port: u16) -> ExitCode {
    let probe = || -> std::io::Result<bool> {
        let addr = SocketAddr::from(([127, 0, 0, 1], port));
        let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(2))?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream
            .write_all(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")?;
        let mut response = String::new();
        stream.read_to_string(&mut response)?;
        Ok(response.starts_with("HTTP/1.1 200"))
    };
    match probe() {
        Ok(true) => ExitCode::SUCCESS,
        _ => ExitCode::FAILURE,
    }
}

/// Finish in-flight requests on Ctrl-C or SIGTERM (what `podman stop` sends).
async fn shutdown_signal() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    let terminate = async {
        if let Ok(mut s) = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            s.recv().await;
        }
    };
    tokio::select! {
        () = ctrl_c => {},
        () = terminate => {},
    }
}
