# Release image for the service. Build: `just image`; test: `just acceptance`. Base images are pinned by digest;
# Dependabot proposes updates. See docs/adr/0005-release-image-and-acceptance.md.

# --- build stage: compile with the same Rust version as rust-toolchain.toml -----------------
FROM docker.io/library/rust:1.100-slim-trixie@sha256:6f14b2b4b278ec0d50aa1d69541c304ce0f95e0f6268487aa9924af1c2e9aebe AS build
WORKDIR /src
COPY . .
# The image already contains Rust 1.100; drop the toolchain file so rustup does not download the
# extra components (rustfmt, clippy, llvm-tools) it lists for development.
RUN rm -f rust-toolchain.toml
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked -p app && cp target/release/app /app

# --- runtime stage: no shell, no package manager, non-root (uid 65532) -----------------------
FROM gcr.io/distroless/cc-debian13:nonroot@sha256:532c7a94f9e96ba9db75eb9388f4227751131c7cb0a411d1a8521af4096135de
ARG VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/num-bbro/rust-factory" \
      org.opencontainers.image.description="Rust software factory example service" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"
COPY --from=build /app /app
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD ["/app", "healthcheck"]
ENTRYPOINT ["/app"]
