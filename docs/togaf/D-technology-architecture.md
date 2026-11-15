# D. Technology Architecture

**Purpose:** Describe the platforms the applications run on: nodes, system software, networks, services.

## Outputs
- Nodes and environments (dev, pilot, production)
- System software
- Technology services

## Content
Factory technology: developer workstations (Arch / Ubuntu-WSL, `id-tech-node-workstation`) with the pinned Rust toolchain and Archi; release images in GHCR (`id-tech-svc-ghcr`); Podman on pilot and production hosts.

The sample reservation service (`id-app-comp-reservation-svc`) runs as a container under Podman
(`id-tech-sw-podman`) on the pilot host (`id-tech-node-pilot`) and production hosts. Epic #17
needs no technology change.

## Open questions
- _none yet_
