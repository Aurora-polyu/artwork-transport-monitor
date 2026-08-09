# Software-Only Demo

This walkthrough is the recommended deterministic portfolio demo. It uses the
clean package's built-in normal sensor sequence and GPS route; it never opens
hardware, starts SMTP, or installs the `hardware` extra.

## 1. Install from a fresh checkout

Requirements: Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked --extra demo --extra development
```

Expected: uv installs the locked Flask/Socket.IO, test, lint, and type-check
dependencies. No Raspberry Pi, serial, or GPIO package is selected.

## 2. Start the dashboard

```sh
uv run artwork-monitor-web
```

Expected: the local server listens at `http://127.0.0.1:8000`. Open that URL
in a browser before running the next step. The Dashboard should show
**SIMULATION MODE**, a connected browser status, and `Not started`.

## 3. Run the deterministic transport session

In a second terminal, from the repository root, run:

```sh
uv run python - <<'PY'
import json
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"


def post(path, payload):
    request = Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request) as response:
        print(path, response.status, response.read().decode())


post("/transport/start", {
    "session_id": "portfolio-demo",
    "started_at": "2026-08-09T12:00:00+08:00",
})
post("/transport/step", {"monotonic_seconds": 0})
post("/transport/step", {"monotonic_seconds": 1})
post("/transport/stop", {
    "ended_at": "2026-08-09T12:00:02+08:00",
})
PY
```

Expected terminal results are one `201` response for start and three `200`
responses for the two steps and stop. The built-in sequence records two normal
environmental readings, two available GPS fixes, and a completed persisted
session/report. It is deliberately a normal-operation demo: no threshold
violation or physical alarm is fabricated.

On the browser Dashboard, the session is selected automatically. You should
see a completed lifecycle, two-point environmental history, a two-fix local GPS
trace, recent events for the session start/GPS fixes/completion, and an enabled
**Open session report** link. The latest filtered values are approximately
22.0 deg C, 50.0 %RH, 506 lux, and 0.000 g gravity deviation; their status is
normal except for the deliberately provisional gravity-calibration label.

## 4. Review the persisted views

- **Dashboard (`/`)**: session summary, history, local route, events, and
  capability states.
- **Report (`/report?session_id=portfolio-demo`)**: one session's persisted
  environmental and GPS summary.
- **GPS (`/gps`)**: select `portfolio-demo` to view the same retained GPS
  history.
- **Transport (`/transport`)**: presents the explicit session controls and
  local live status. It does not begin monitoring by itself. Treat it as a
  simulation-oriented integration preview rather than a fully accepted
  interactive operational workflow.

To repeat the exact scenario, stop the web server with `Ctrl+C` and start it
again. The dashboard creates a new temporary demo database and finite simulated
sources for each server process.

## Screenshot plan

Capture browser screenshots only after the completed session is visible:

1. **Dashboard overview** — include the `SIMULATION MODE` badge, completed
   lifecycle, session details, four metric cards, two-point history, local GPS
   trace, and recent events. This is the primary README/portfolio image.
2. **Session report** — show the `portfolio-demo` report's normal environmental
   summary and available GPS count to demonstrate persisted, session-scoped
   reporting.
3. **Capability panel** — include the panel that labels sensors/GPS as
   simulated and not physically validated. Use this as the evidence-boundary
   companion image if space permits.

Do not present a browser connection, local route trace, or simulated readings
as proof of a physical device, on-road GPS tracking, or hardware calibration.

## Demo limitations

- The recommended path demonstrates normal operation and meaningful lifecycle,
  realtime, GPS, persistence, and reporting events; it intentionally does not
  simulate a hardware alarm in the browser.
- The dashboard is a local development server, not a production deployment.
- Raspberry Pi I2C sensors, GPIO buzzer, serial GPS, camera/TFLite integration,
  environmental calibration, and route-deviation validation remain deferred.
- Browser acceptance of every redesigned Transport-page lifecycle, error, and
  reconnection path remains deferred; do not use it as hardware-control proof.
