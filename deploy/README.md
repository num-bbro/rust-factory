# Deployment

Released images go to the **pilot** first, then, after a human decides, to **production**,
one host at a time. Every deploy is health-checked and rolled back automatically on failure.
Design: [ADR 0006](../docs/adr/0006-pilot-and-rollout-with-quadlet.md).

```bash
just deploy pilot 0.1.0     # pull the release, pin its digest, deploy, health-check (rollback on failure)
just deploy-status          # what runs where, systemd state, /health
just promote 0.1.0          # HUMAN GATE: pilot must run 0.1.0 healthily; then production, host by host
```

## Files
| File | What |
|---|---|
| `hosts/pilot.txt`, `hosts/production.txt` | Hosts per environment: `name target port` |
| `rust-factory.container.in` | Podman Quadlet unit template (one systemd service per host) |
| `../scripts/deploy.sh` | The deploy logic; `just` recipes call it |

On each host: the unit lives at `~/.config/containers/systemd/rust-factory-<name>.container`,
the current and previous image in `~/.local/state/rust-factory/<name>/`.

## Simulated hosts (now)
`target = local` runs the "host" as a systemd user service on this machine, on its own port
(pilot 18081, prod-1 18082, prod-2 18083). This exercises the real mechanics (Quadlet, systemd,
health checks, rollback) without servers. Local user services stop when you log out.

## Adding a real VM
1. On the VM (Ubuntu or similar), as a dedicated user, e.g. `deploy`:
   ```bash
   sudo apt-get install -y podman curl          # Podman ≥ 4.4 (Quadlet), curl for health checks
   sudo loginctl enable-linger deploy            # keep user services running without a login
   ```
2. Make SSH key login work from the machine that deploys: `ssh deploy@<vm> true` must succeed
   without a password prompt.
3. Add a line to the environment file, e.g. in `hosts/production.txt`:
   ```text
   prod-3   ssh:deploy@10.0.0.13   8080
   ```
4. Deploy as usual. The first deploy to a new host has no previous version: if it fails, the
   service is stopped and removed rather than rolled back.

The image is public on GHCR, so VMs need no registry login. If it ever becomes private, run
`podman login ghcr.io` once on each VM.

**Not yet tested:** the SSH transport (no VM exists yet). The local transport is fully exercised.
