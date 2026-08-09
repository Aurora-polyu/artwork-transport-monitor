# Artwork Transportation Monitoring

A software-first reconstruction of an AP30023 coursework project about
protecting fine-art items during transport. The original coursework system
under [`sotheby/`](sotheby/) called for
environmental monitoring, artwork identification, and a web interface for
historical and live information. It is retained as an audited reference, not
as the supported runtime. The coursework wording is retained in
[`AP30023_project_1_course_request.md`](AP30023_project_1_course_request.md).

The clean implementation in [`src/artwork_monitor/`](src/artwork_monitor/)
separates deterministic monitoring logic from optional adapters. Its goal is a
laptop-safe, testable portfolio demonstration of the transport workflow. It is
not a claim that the original physical system has been revalidated.

## Closure status and evidence boundary

The clean software rebuild is complete for deterministic, software-only use:
the package, simulation, persistence, reports, local web views, and automated
checks are the supported evidence. This is distinct from both the original
coursework tree and a physical deployment.

- **Original coursework system:** preserved under `sotheby/`; its observed
  hardware coupling and defects are documented, not endorsed as the clean
  runtime.
- **Clean reconstructed software:** `src/artwork_monitor/` and `tests/`; it
  uses explicit lifecycle control and session-scoped persisted data.
- **Deterministic simulation:** the supported demo path; it supplies scripted
  sensor/GPS data and never proves a physical device, calibrated threshold, or
  real alert.
- **Hardware revalidation:** not performed. See
  [`docs/hardware-revalidation-checklist.md`](docs/hardware-revalidation-checklist.md)
  before any Raspberry Pi or device-facing claim.

The redesigned Transport page is a local, simulation-oriented integration
preview. Its controls and live presentation have not been fully validated as a
complete interactive operational workflow; follow-up frontend integration and
browser acceptance remain deferred.

## What is included

- Deterministic simulated sensor and GPS inputs, threshold evaluation, EWMA
  filtering, immediate/prolonged condition tracking, and an explicit transport
  lifecycle.
- SQLite session persistence, per-session CSV export, deterministic Markdown
  reports, and in-memory notification dispatch for demos/tests.
- A local Flask + Socket.IO dashboard with transport, artwork-check, GPS, and
  report views. It is explicitly labelled **simulation mode**.
- Hardware-neutral ports plus optional serial-NMEA GPS and GPIO alarm adapters;
  importing or running the demo does not require Raspberry Pi packages.

See [`docs/clean-rebuild.md`](docs/clean-rebuild.md) for the architecture,
workflow, thresholds, boundaries, and repository map. The detailed source
audit is kept separately in [`docs/legacy-system-spec.md`](docs/legacy-system-spec.md)
and [`docs/hardware-inventory.md`](docs/hardware-inventory.md).
For a reproducible browser walkthrough and screenshot plan, see
[`docs/demo.md`](docs/demo.md).

## Quick start

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked --extra demo --extra development
uv run artwork-monitor --profile demo
```

The demo runs a finite normal transport session and writes ignored SQLite/CSV
artifacts under `instance/`. It uses only the `demo` and `development` extras;
do not install the `hardware` extra for this workflow.

Start the local dashboard in a second terminal:

```sh
uv run artwork-monitor-web
```

Open <http://127.0.0.1:8000>. The dashboard and simulated transport controls
persist sessions and publish live transport/GPS events locally through
Socket.IO. Stop the local server with `Ctrl+C` when the demo is complete.

## Quality checks and CI

```sh
uv lock --check
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

GitHub Actions runs the same software-only checks on pushes and pull requests;
see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Validation boundary

The clean package is validated by deterministic software tests and local demo
flows. On-device I2C sensor reads and calibration, GPIO buzzer behavior, serial
GPS hardware, camera/TFLite model integration, startup/shutdown on-device
lifecycle, real alerts, and any claim about physical environmental protection
or route deviation remain deferred. The adapters and legacy inventory are
references for later hardware work, not evidence of physical validation.
