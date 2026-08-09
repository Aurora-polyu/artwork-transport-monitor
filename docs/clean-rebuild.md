# Clean Rebuild Guide

## Purpose and context

The original AP30023 coursework scenario was a Sotheby's fine-art transport
monitor: maintain suitable environmental conditions, identify two artwork
markers, and expose historical/live information in a web interface. The
original snapshot remains in `sotheby/` for evidence and comparison; it is not
the recommended runtime path. Its process-global state, eager hardware startup,
and legacy behaviour are documented in
[`legacy-system-spec.md`](legacy-system-spec.md).

`artwork_monitor` is the clean, software-only rebuild. It preserves the
meaningful monitoring workflow while making lifecycle, persistence, timestamps,
and simulation explicit and testable.

## Architecture

```text
domain              Typed readings, thresholds, sessions, violations
application         Filtering, monitoring, reports, workflows
ports               Interfaces for sensors, GPS, alarms, persistence, notices
adapters            Simulated sources; SQLite/CSV; optional serial/GPIO
web                 Flask routes, Jinja views, local Socket.IO events
```

The core has no clocks, threads, network clients, or Raspberry Pi imports.
`MonitoringService.step(monotonic_seconds)` is driven by supplied time and
sources. `TransportSessionWorkflow` follows `not_started → running →
completed`; completion reloads its stored session, exports one CSV, and produces
one report.

## Software-only workflow

Use the locked `demo` and `development` extras:

```sh
uv sync --locked --extra demo --extra development
uv run artwork-monitor --profile demo
uv run artwork-monitor --artwork-demo
uv run artwork-monitor-web
```

The CLI transport demo uses finite normal sensor readings and creates ignored
runtime artifacts beneath `instance/`. The web app constructs its own temporary
demo SQLite database unless dependencies are injected. It never starts hardware,
background monitoring, or notifications merely by being created.

The dashboard at `http://127.0.0.1:8000` provides session-scoped views and
local Socket.IO events for transport cycles, available GPS fixes, violations,
and completion/report readiness. Its browser connection status is not a claim
that any physical device is connected.

## Monitoring behaviour

Environmental values use EWMA filtering: temperature/humidity use alpha=0.1
and light uses alpha=0.3. Missing values remain missing and do not invent a
reading.

| Measurement | Normal range/rule | Notes |
| --- | --- | --- |
| Temperature | 18-27 deg C inclusive | Below/above is a violation. |
| Humidity | 25-75 %RH inclusive | Below/above is a violation. |
| Light | <= 6000 lux | Above is a violation. |
| Motion | gravity deviation from 1 g | Thresholds are provisional pending calibration. |

Immediate violations are retained per monitoring cycle. Environmental conditions
may also become a prolonged violation after four continuous seconds; motion is
not part of prolonged environmental tracking. Timestamps are recorded in
`Asia/Hong_Kong` (`+08:00`).

## Persistence, reports, and web views

Each completed clean transport session is stored in SQLite as session-scoped
records. The workflow exports a CSV for that same session and generates a
deterministic Markdown report with environmental summaries, GPS availability,
and immediate/prolonged violations kept distinct. The web layer exposes:

- Dashboard and session data: `/` and `/api/sessions/<id>/dashboard-data`
- Transport actions/status: `/transport`, `/transport/start`, `/transport/step`,
  `/transport/stop`
- Reports and GPS history: `/report`, `/api/report/data`, `/gps`,
  `/api/gps/history`
- Artwork check: `/check`

Artwork-check state is an independent, in-memory workflow. The clean demo uses
finite camera/detector sequences; it does not load a real camera or TFLite
model. See [`artwork-camera-workflow-design.md`](artwork-camera-workflow-design.md).

## Optional hardware adapters

`SerialNmeaGPSFixSource` can pull active RMC NMEA fixes from `/dev/serial0`,
and `GpioAlarmOutput` can control an instance-owned GPIO output. They are
optional adapters behind ports and imported lazily. They need the `hardware`
extra and appropriate Raspberry Pi hardware; they are not enabled by the demo
or CI.

The hardware map, legacy device assumptions, and calibration cautions are in
[`hardware-inventory.md`](hardware-inventory.md). In particular, the clean
gravity-deviation representation must not be presented as validated vibration
or damage detection.

## Repository map

```text
src/artwork_monitor/     Clean package
tests/                   Deterministic software tests
docs/                    Clean and legacy design/reference documents
sotheby/                 Preserved original coursework snapshot
.github/workflows/       Software-only GitHub Actions QA
instance/                Ignored local demo artifacts
```

## Testing and limitations

Run `uv lock --check`, `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`, and `uv run mypy`. GitHub Actions runs these
checks using only the `demo` and `development` extras.

Software validation does not replace physical validation. Outstanding work
includes Raspberry Pi I2C sensor and display checks, GPIO/buzzer electrical
behaviour, serial GPS reception, camera/model compatibility and calibration,
environmental calibration, route-deviation validation, and production web/email
operations. The clean rebuild deliberately does not perform real SMTP or device
startup in normal tests or demos.
