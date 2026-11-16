# Release image for the service. Build: `just image`; test: `just acceptance`. Base images are pinned by digest;
# Dependabot proposes updates. See docs/adr/0005-release-image-and-acceptance.md.

# --- build stage: compile with the same Rust version as rust-toolchain.toml -----------------
FROM docker.io/library/rust:1.100-slim-trixie@sha256:e9d95b74296f7126a83ae3d041aeaba1ff4c478f13abc5cc034fcf7c131c3d4a AS build
WORKDIR /src
COPY . .
# The image already contains Rust 1.99; drop the toolchain file so rustup does not download the
# extra components (rustfmt, clippy, llvm-tools) it lists for development.
RUN rm -f rust-toolchain.toml
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked -p app && cp target/release/app /app

# --- runtime stage: no shell, no package manager, non-root (uid 65532) -----------------------
FROM gcr.io/distroless/cc-debian13:nonroot@sha256:cb87acc574abe719b6e5c547384defa2f7b1f24af9605d3f618cf852495d8be2
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
