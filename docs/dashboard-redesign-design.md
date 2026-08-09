# Task 10C.1 — Live Dashboard Redesign Design

## Purpose and boundary

Redesign `GET /` as a polished, light-theme operational dashboard for the clean
Flask/Jinja application. It must present the current transport and artwork
workflow truthfully, remain useful after a browser reconnect, and make it clear
that this is a **SIMULATION MODE** interface. This is a design specification
only: it changes no routes, events, templates, CSS, JavaScript, domain logic,
thresholds, or tests.

The supplied mockup informs the visual language only: warm surface, generous
white space, quiet borders, compact metric cards, and clear information bands.
It is not a source of route names, artwork identity, ETA, distance, equipment
health, threshold values, or map content.

### Non-negotiable domain presentation

- Temperature is normal from **18 to 27 °C inclusive**.
- Humidity is normal from **25 to 75 %RH inclusive**.
- Light is normal at **6000 lux or below**.
- Motion is **gravity deviation (g)**, never RMS vibration. Its moderate and
  excessive thresholds are shown only as *provisional pending hardware
  calibration and validation*.
- Displayed timestamps are rendered in `Asia/Hong_Kong` with an explicit
  `+08:00` offset (for example, `2026-08-09 12:00:00 +08:00`).
- No dashboard language may imply physical sensor, GPS, camera, storage, or
  realtime hardware validation. “Connected” is reserved for the browser's
  Socket.IO connection, not a physical device.

## Information architecture and desktop layout

The page retains the existing global navigation but makes Dashboard the active
destination. The main content uses a centred max-width of approximately
1440 px, a 24 px desktop gutter, and a 24 px vertical grid gap.

```text
Global header: brand | Dashboard / Transport / GPS / Artwork Check / Reports
Dashboard masthead: title + SIMULATION MODE + lifecycle pill + live connection
Session / artwork context strip
Four equal metric cards: temperature | humidity | light | gravity deviation
Two-column content: environmental history (2/3) | local route + events (1/3)
System-health panel                                      Report + artwork block
```

1. **Header and masthead.** A warm-white header holds the existing product
   name and navigation. The dashboard masthead contains “Live Dashboard”, a
   persistent amber outlined `SIMULATION MODE` badge, the lifecycle state, and
   a small realtime indicator. Lifecycle text is `Not started`, `Running`, or
   `Completed`—never “in transit” unless that domain state is added later.

2. **Session and artwork context strip.** Four labelled fields: current or
   selected `Session ID`, `Started`, `Completed`, and `Artwork workflow`.
   Fields with no value render an em dash with “No active session” rather than
   fabricated data. The artwork field is a compact count/status summary and a
   `/check` link; it explicitly says that artwork workflow state is in memory
   and is not linked to a transport session.

3. **Metric-card row.** Four consistent cards show the most recent available
   reading, its unit, a semantic status, the approved environmental range or
   limit, and a tiny local SVG sparkline. The gravity-deviation card has a
   short calibration-provisional note instead of declaring it safe/validated.
   A missing field displays `Unavailable` with no plotted point. Before a
   reading is received, all cards show `Awaiting first cycle`.

4. **Environmental history.** A large card with an inline SVG time-series
   chart; a plain-text recent window selector is unnecessary because the
   application exposes the selected session's complete retained record set,
   not a rolling two-hour query. Plot temperature, humidity, light, and gravity
   deviation as separately toggleable series (all on initially) so unlike
   units are not misleadingly compared on one scale. The chart plots only
   available values, uses time on the x-axis, gives each series its own labelled
   axis/readout treatment, and includes the approved environmental limits as
   subtle dashed reference lines. The motion legend says “gravity deviation (g)
   — provisional threshold.”

5. **Transport route.** A local, offline-capable coordinate plot—not a map—is
   labelled `GPS trace (local coordinate view)`. It normalizes the returned
   latitude/longitude extent into an SVG viewport, draws chronological points
   and a line, marks first/latest fixes, and shows coordinate/time tooltips or
   an accessible accompanying list. It does not name a route, infer a
   destination, calculate distance, offer map tiles, or claim route adherence.
   Zero valid points render `No GPS fixes recorded for this session`; one point
   renders a single point with `One fix; trace unavailable`.

6. **Recent event timeline.** A compact chronological feed contains only
   actual application events: transport lifecycle changes, GPS fixes, emitted
   condition violations, report readiness, and artwork workflow/status events.
   It shows the event timestamp and the supplied condition/value/threshold when
   present. “No events yet” is distinct from lost connectivity. A capped
   in-browser live list is acceptable during a run; the selected-session HTTP
   fallback described below makes the persisted transport portion reload-safe.

7. **System health.** This is a capability/connection panel, not an invented
   health-monitor. It has these rows: `Runtime mode`, `Sensor input`, `GPS
   input`, `Artwork workflow`, `Session storage`, and `Realtime connection`.
   Example truthful text in the supplied demo wiring is “Simulation source”,
   “Available” only when the application reports availability, and “Connected”/
   “Disconnected” only for the Socket.IO client. It must not use “healthy” for
   a simulated component. An explanatory footnote states that physical hardware
   has not been validated after modernization.

8. **Session report access.** When the selected/current session has completed,
   show a primary `Open session report` link to the event-provided `report_url`
   or `/report?session_id=<id>`. While running, show `Report available after
   completion`; with no session, show `Select or start a session`. The dashboard
   never links to a report without its session ID and never aggregates reports.

9. **Artwork workflow.** A compact panel lists the actual artwork `lot`,
   `name`, and `in`/`out` state exposed by `/check/status`/events, with a link to
   `/check` for control and detail. It displays `Checking active` or `Checking
   idle`, not camera-stream or recognition-health claims. Empty data renders
   `No artwork workflow data available`.

## Visual system

- **Palette:** page `#F7F4EE` or similar warm off-white; cards `#FFFEFB`;
  charcoal text; muted stone-grey metadata; dark olive/teal for normal;
  ochre/amber for caution; restrained red for a violation; neutral slate for
  unavailable/disconnected. Colour never carries status alone: every badge has
  text and an icon/shape.
- **Typography:** use a local/system font stack for UI text; use the existing
  local-safe serif stack only for restrained brand/headline treatment. No web
  font or CDN request. Recommended scale: 12 px label, 14 px metadata, 16 px
  body, 22–26 px card value, 30–36 px masthead.
- **Spacing and hierarchy:** 8 px base unit; cards use 20–24 px padding,
  12–16 px internal gaps, 14–16 px corner radius, a 1 px low-contrast border,
  and a very soft elevation. Hero/context panels have the strongest presence;
  metric cards are secondary; timeline and health rows are deliberately quiet.
- **Charts:** SVG generated by local vanilla JavaScript, with no Chart.js,
  Leaflet, tile service, or external asset. SVG preserves crisp export/README
  screenshots and can include native text labels and focusable data points.

## Responsive behaviour

At desktop width (>= 1200 px), use the layout above: four metrics in one row,
history and the route/events column at 2:1, and health/report/artwork in a
bottom grid. At tablet width (768–1199 px), use two metric columns; history,
route, timeline, health, report, and artwork each become full-width blocks in
that reading order. At mobile width (<768 px), preserve the masthead badges,
stack every panel in one column, make the header navigation horizontally
scrollable or collapsible without JavaScript dependency, and give SVG panels a
fixed readable minimum height with horizontal legend wrapping. Tables become
label/value rows. No essential status, report link, or simulation disclaimer may
be hidden at any breakpoint.

## Realtime and HTTP data mapping

The dashboard treats Socket.IO as the live enhancement; HTTP is the source of
record on a load/reload. It renders the initial skeleton immediately, fetches
what is available, then connects Socket.IO. All event handlers ignore a
session-scoped event whose `session_id` differs from the actively displayed
session, except artwork workflow events, which are deliberately global/in-memory
in the current contract.

| Component | Initial source | Socket.IO events | Existing HTTP fallback | Empty / unavailable / disconnected state |
|---|---|---|---|---|
| Header / lifecycle | `state_snapshot.transport` | `transport_started`, `transport_completed` | `GET /transport/status` gives lifecycle only | `Not started`; on socket loss, lifecycle remains last-known and shows `Live updates disconnected` |
| Session context | `state_snapshot.transport.session_id`, selected persisted session | `transport_started`, `transport_completed`, `report_ready` | No full session-context endpoint exists | Em dash / `No active session`; see Gap 1 |
| Temperature / humidity / light / gravity cards | Latest selected-session record, or none | `transport_cycle` | No raw sensor-record endpoint exists; `/api/report/data` is summaries only | `Awaiting first cycle` or `Unavailable`; see Gap 1 |
| Environmental history | Selected-session ordered records | `transport_cycle` appends latest point | No raw sensor-history endpoint | Empty chart explanation; see Gap 1 |
| GPS trace | Selected-session GPS points | `gps_update` appends a point | `GET /api/gps/history?session_id=<id>` | `No GPS fixes recorded`; single-point trace message; disconnected retains points |
| Recent events | Selected-session persisted events plus page-local events | `transport_started`, `transport_cycle`, `gps_update`, `violation`, `transport_completed`, `report_ready`, all three artwork-check events, `artwork_status_changed` | No event-history endpoint | `No events yet`; socket loss gets a persistent disconnected notice; see Gap 1 |
| System health | Declared runtime/capability metadata; browser `socket.connected` | Socket `connect`, `disconnect`, `connect_error` (client lifecycle, not server-published) | No health/capability endpoint | `Status unavailable`; never assume real or healthy; see Gap 2 |
| Report access | `state_snapshot.session_ids` and selected ID | `report_ready`, `transport_completed` | `/report?session_id=<id>` and `GET /api/report/data?session_id=<id>` | Completion-required / no-session copy; do not fetch report data until an ID is known |
| Artwork workflow | `state_snapshot.artwork`; optionally refresh on page load | `artwork_check_started`, `artwork_check_stopped`, `artwork_status_changed` | `GET /check/status` | `No artwork workflow data available`; socket loss leaves last-known state and links to `/check` |

`transport_cycle.reading` contains `timestamp`, `temperature_c`,
`humidity_percent_rh`, `light_lux`, and `gravity_deviation_g`; it also provides
`immediate_conditions` and `prolonged_conditions`. `violation` carries the
condition, observed value, threshold, unit, kind, and timestamp. `gps_update`
only represents available fixes; absence of this event does not prove GPS is
unavailable.

## Status semantics

Environmental status is calculated in the client from the same inclusive rules
as the backend and is confirmed by any supplied violation event. `Normal` means
the current available reading is within the approved environmental boundary.
`Violation` means a value is outside that boundary or a matching event has been
received. `Unavailable` means the field is `null`/not supplied; it is not
normal. For gravity deviation, show `Provisional` alongside the backend's
moderate/excessive event categories, never `validated normal`.

Lifecycle is independent of metric status. Artwork `in`/`out` is a legacy
in-memory workflow state and must not be rendered as transport custody proof.

## Loading, error, and reconnection behaviour

1. Render card and chart skeletons with labelled `Loading dashboard state` text;
   do not use fabricated zeroes or sample values.
2. Apply `state_snapshot` when it arrives. Fetch selected-session history and
   GPS only after the session ID is known.
3. If an HTTP request fails, show an inline panel-specific error and retain any
   last successful data. A `404` session selection clears that selection and
   explains that the session is unavailable.
4. On Socket.IO `disconnect` or `connect_error`, expose a non-blocking
   `Live updates disconnected` banner, preserve the last timestamp, and offer
   a local `Retry connection` action. HTTP navigation/report access remains
   available.
5. On reconnect, replace optimistic live state with the new `state_snapshot`,
   then re-fetch the selected-session history to resolve missed cycles/events.

## Contract gaps and smallest proposed interface additions

### Gap 1 — reload-safe dashboard session timeline

The current API can return report aggregates and GPS points but cannot return
ordered sensor readings, violations, session start/end, or persisted events.
Consequently, a dashboard can chart only cycles received after the current
browser opened and cannot rebuild a selected session's timeline.

**Smallest addition:** `GET /api/sessions/<session_id>/dashboard-data`, sourced
solely from the existing persisted `StoredTransportSession`. Return the session
ID, canonical `started_at`/`ended_at`, and ordered records containing
`sequence`, a canonical reading timestamp, the four existing reading fields,
GPS status/coordinates when present, and the existing immediate/prolonged
violation payloads. It must neither add route metadata nor invent historical
artwork linkage. This single endpoint supplies initial context, metrics,
environmental history, GPS fallback, and the transport portion of recent
events. It returns 404 for an unknown session.

### Gap 2 — truthful runtime/capability status

`WebDependencies` currently exposes services but not their declared mode or
component availability. The dashboard therefore cannot truthfully distinguish
the supplied simulated adapters from another injected implementation, or state
whether persistence is available without probing and guessing.

**Smallest addition:** add a read-only `runtime_capabilities` value to
`WebDependencies` and include it in `state_snapshot` (or expose it at one
`GET /api/dashboard/capabilities` endpoint). It should declare only known
facts: runtime mode (`simulation` for `create_demo_dependencies`), sensor/GPS/
artwork source type, and storage availability. The browser alone owns Socket.IO
connection status. Do not call an undeclared component “healthy.”

### Gap 3 — canonical realtime timestamps

Reports normalize timestamps through `format_hong_kong_timestamp`, while
`transport_cycle`, `gps_update`, and `violation` currently publish raw
`.isoformat()` values. A caller can provide a non-Hong-Kong aware timestamp, so
the live UI cannot guarantee the requested `Asia/Hong_Kong +08:00` format.

**Smallest addition:** serialize all realtime timestamps through the existing
`format_hong_kong_timestamp` helper, without changing stored instants or event
names. This is a presentation-contract normalization, not a timezone conversion
of the underlying science data.

## Task 10C.2 likely file changes

- `src/artwork_monitor/web/templates/base.html` — light shell, nav, socket
  bootstrap/reconnection hooks.
- `src/artwork_monitor/web/templates/index.html` — dashboard semantic markup
  and empty-state containers.
- `src/artwork_monitor/web/static/style.css` — full local responsive visual
  system and SVG/chart panel styling.
- A new local dashboard JavaScript file under
  `src/artwork_monitor/web/static/` — state store, HTTP fetches, Socket.IO
  handlers, SVG charts/trace, accessibility, and error states.
- `src/artwork_monitor/web/app.py` — only if the three proposed small contract
  additions are approved.
- `src/artwork_monitor/web/services.py` — only if declared runtime
  capabilities are approved.
- `tests/test_web.py` and `tests/test_realtime.py` — endpoint payload,
  timestamp, fallback, and rendered dashboard coverage; likely a focused
  dashboard-client/unit test if JavaScript testing infrastructure is added.

No React/Vue, CDN, external map tiles, hardware drivers, route-deviation logic,
artwork/session association, or threshold/calibration change belongs to Task
10C.2 unless separately approved.
