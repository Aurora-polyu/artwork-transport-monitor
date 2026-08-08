# Legacy System Specification

## Scope and evidence

This document describes the checked-in Python/Flask application under `sotheby/` as it exists in the original coursework snapshot. It is a behavioral reference, not a redesign. Runtime-generated logs show an older execution on 2025-11-27, but several `.py` files are newer than those logs; where they disagree, this specification treats the current source as authoritative and calls out the mismatch.

The coursework mission is environmental protection, dark-enclosure/intrusion monitoring, two-artwork camera recognition, and a historical/real-time web UI (`AP30023_project_1_course_request.md`, “Basic Requirements”).

## Runtime composition and shared state

`app.create_app()` constructs a single Flask application and one process-global instance of each service (`sotheby/app.py:create_app`). It initializes SQLite, email, alerts, GPS, buzzer, sensors, camera, and reports; attaches those instances as ad-hoc attributes on `app`; registers four blueprints; then starts daemon/background loops.

Important mutable state is process-local and global:

- `sensor._sensor_manager` and `sensor._socketio` are module globals used by all transport requests (`sotheby/sensor.py:init_sensor_manager`, `start_transport`, `stop_transport`).
- `app.transport_active` duplicates `SensorManager._running`; `/transport/status` returns both, while the email-monitoring loop considers transport active if the app flag says so (`sotheby/app.py:sensor_monitoring_loop`; `sotheby/sensor.py:transport_status`).
- `hardware.alarm_buzzer.buzzer` and `hardware.buzzer_integration._buzzer_initialized` are global singleton state shared by environmental and GPS alerts.
- `CameraService.art_states` and `system_state` are shared across every browser/client and disappear on process restart (`sotheby/services/camera_service.py:CameraService.__init__`).
- `GPSService.latest_fix`, route, current segment, and deviation flag are held by its daemon thread; route/history/events also use the shared relative-path SQLite database (`sotheby/services/gps/gps_service.py:GPSService`).
- `AlertService.violation_state` is shared across all transport sessions and is not reset by start or stop (`sotheby/services/alert_service.py:AlertService.__init__`, `reset_violation_tracking`; `sotheby/sensor.py:start_transport`, `stop_transport`).

## Environmental monitoring

### Samples and filtering

`SensorManager.start()` resets the three EWMA filters, opens a new CSV, and starts one daemon sampling thread. Repeated starts while running return without opening another CSV. `stop()` clears the in-memory sample window and closes the CSV (`sotheby/sensor.py:SensorManager.start`, `stop`).

The loop targets one cycle every 2.0 seconds and retains 60 samples (approximately two minutes). It subtracts processing time from the sleep, so slow processing lengthens the effective interval (`sotheby/sensor.py:SAMPLE_PERIOD`, `MAX_SAMPLES`, `SensorManager._run_loop`). Each sample contains:

`timestamp`, `temperature`, `humidity`, `light_intensity`, `accel_x`, `accel_y`, `accel_z`, `vibration`, `inclination_deg`, plus the derived in-memory-only `vibration_status` (`sotheby/sensor.py:SensorManager._read_all_sensors`, `_run_loop`). Timestamps are timezone-aware Hong Kong ISO strings (`sotheby/utils/time_utils.py:isoformat_hk`).

Temperature and humidity use EWMA factor 0.1; light uses factor 0.3. On the first value the filtered value equals the raw value. Filters ignore `None` but keep their previous internal value; the emitted sample remains `None` for a failed read because `SensorFilter.update(None)` returns `None`. Vibration below 0.02 g is forced to zero and otherwise is unfiltered (`sotheby/sensor.py:SensorFilter`, `SensorManager._run_loop`). Acceleration and inclination are unfiltered.

Thresholds in the active backend are:

| Field | Normal/abnormal rule | Unit used by UI/code |
|---|---|---|
| Temperature | abnormal below 18 or above 27 | °C |
| Humidity | abnormal below 25 or above 75 | % RH |
| Light intensity | abnormal above 6000 | lux |
| Vibration | moderate at 15.0; excessive at 20.0 | code labels it g, with “RMS (conceptual)” comment |

Source: `sotheby/sensor.py:THRESHOLDS`. Comparisons are strict for environmental min/max (`<`/`>`), while vibration levels use `>=` in the UI/status calculation (`sotheby/hardware/alarm_buzzer.py:BuzzerAlarm.check_thresholds_and_trigger`; `sotheby/sensor.py:SensorManager._run_loop`; `sotheby/templates/transport.html:setStatus`).

The transport template contains stale initial defaults (temperature max 25, light max 150, vibration moderate 10) that are replaced only after the first `sensor_data` event. The report template's mock fallback repeats the stale values (`sotheby/templates/transport.html:thresholds`; `sotheby/templates/report.html:getMockData`).

### Sensor interpretation

- SHT4x conversion is `-45 + 175 * raw/65535` °C and `-6 + 125 * raw/65535` % RH, with humidity clamped to 0–100. It tries high-, medium-, then low-precision commands with 10/5/2 ms waits. CRC bytes are received but never validated (`sotheby/sensor.py:Sensors.read_all`).
- VEML7700 light is little-endian raw count multiplied by 0.2688 lux/count (`sotheby/sensor.py:Sensors.read_all`).
- LIS3DSH axes are signed 16-bit values multiplied by `8/65536`, described by the code as a ±8 g range. `vibration = abs(sqrt(ax²+ay²+az²)-1)` and inclination is `acos(az/total)` in degrees (`sotheby/sensor.py:Sensors.read_all`). This is deviation from 1 g, not RMS vibration.
- Accelerometer reads occur only when the light reading is above 0.1 lux. At or below 0.1 lux all axes, vibration, and inclination are set to 0.0. If light is unavailable, acceleration is also unavailable (`sotheby/sensor.py:Sensors.read_all`). Consequently, dark-enclosure operation suppresses motion/intrusion sensing.

### Display

On startup the LCD shows “Transport Monitor / Starting up...” for two seconds, then “System Ready / Waiting for data” for one second. Start and stop show status messages. Every sample displays temperature/humidity on line 1 and light/vibration on line 2; any missing one of those four produces an error screen. Values are truncated to 16 characters per line (`sotheby/hardware/display.py:I2CDisplay.show_startup_message`, `show_sensor_data`, `show_status`; `sotheby/sensor.py:SensorManager._run_loop`).

## Alert behavior

There are two independent environmental paths plus GPS alerts.

1. **Immediate local buzzer:** every sensor cycle calls `check_transport_alarms`. Any temperature/humidity/light violation or `vibration_status == "excessive"` starts the shared buzzer immediately; a fully normal sample stops it. This path does not email, emit a web alert, or persist an event (`sotheby/sensor.py:SensorManager._run_loop`; `sotheby/hardware/alarm_buzzer.py:BuzzerAlarm.check_thresholds_and_trigger`). A missing temperature/humidity/light value raises during comparison; the wrapper catches it, and any existing alarm state may remain unchanged (`sotheby/hardware/buzzer_integration.py:check_transport_alarms`).
2. **Prolonged temperature/humidity/light alert:** a separate daemon thread polls the latest sample every second only while transport is active. After a continuous wall-clock violation reaches four seconds, it emits one Socket.IO `alert`, attempts one email, and appends an event to CSV and SQLite. It sends no additional alert until a normal observation resets that field. Vibration is not checked by this path, and it does not request the buzzer (`sotheby/app.py:sensor_monitoring_loop`; `sotheby/services/alert_service.py:check_prolonged_violations`, `trigger_alert`). Because the same 2-second sample is inspected repeatedly, duration is wall time, not four seconds of distinct readings.
3. **GPS route deviation:** the first off-route fix in an episode emits/persists an alert, attempts email, and starts the buzzer indefinitely. Every subsequent off-route RMC fix calls `trigger_alert` again with email disabled, so it still broadcasts and persists repeated “still deviated” events. An on-route fix stops the shared buzzer (`sotheby/services/gps/gps_service.py:GPSService.check_route_deviation`).
4. **Start/stop location check:** transport start and stop compare the current fix with the nearest route *waypoint* (not the route line), using a separate hardcoded 500 m limit. If exceeded, an alert is emitted/persisted/emailed and the buzzer is scheduled to stop after five seconds (`sotheby/sensor.py:_check_route_distance_alert`; `sotheby/services/alert_service.py:trigger_alert`).

The single global buzzer has no ownership or priority. A GPS recovery, route clear, transport stop, five-second timer, or environmental-normal sample can silence another still-active alarm (`sotheby/services/alert_service.py:stop_buzzer`; `sotheby/services/gps/gps_tracking.py:api_set_route`, `api_clear_data`, `api_clear_route_only`). The physical pattern is a 1 kHz PWM tone at 50% duty for 0.3 seconds followed by approximately 0.5 seconds between beeps; a digital pulse fallback is used if PWM fails (`sotheby/hardware/alarm_buzzer.py:BuzzerAlarm._beep`, `_alarm_pattern`).

## GPS and route tracking

`GPSService` is a daemon thread that repeatedly opens `/dev/serial0` at 9600 baud with a five-second serial timeout, retrying connection every five seconds forever. It accepts NMEA lines containing `RMC`, parses them with `pynmea2`, and uses only active (`status == "A"`) latitude, longitude, and NMEA time. Every valid RMC is inserted into SQLite without rate limiting; invalid fixes set status to “Scanning...” (`sotheby/services/gps/gps_service.py:connect_serial`, `run`). Speed and heading are not retained even though the email template has fields for them.

After serial connection succeeds, the service loads the active route. A route comprises a name, JSON waypoint list, and maximum deviation in metres. Deviation is cross-track distance from the infinite great-circle line for the current segment. The service starts at segment 0, advances when within 200 m of its endpoint, never moves backward, and stops checking after the final segment (`sotheby/services/gps/gps_service.py:load_route_from_db`, `check_route_deviation`, `get_cross_track_distance`). GPS deviation monitoring is not gated by `transport_active`; it operates whenever a route and valid fixes exist.

The browser polls the current fix every two seconds and persisted alert events every five seconds; history and route are fetched only when the map initializes. Map tiles come from OpenStreetMap over the network. It defaults to London coordinates until a fix arrives (`sotheby/templates/gps.html:initMap`, `fetchRealtime`, `fetchHistory`, `fetchRoute`, `fetchEvents`).

Route creation accepts any JSON POST with at least two waypoints, stores a UI-default name “Task 1” and 500 m maximum, then reloads the GPS service. “Clear route” stores an empty route row rather than deleting it; “reset task” deletes GPS history, sensor events, and active route, but does not clear `latest_fix` (`sotheby/services/gps/gps_tracking.py:api_set_route`, `api_clear_route_only`, `api_clear_data`; `sotheby/data_access/database.py:set_active_route`, `clear_gps_data`).

## Camera, TFLite, and artwork workflow

`CameraService` loads `models/model.tflite`, reads its input shape/dtype, then opens OpenCV camera index 0. Source requests buffer size 1, 30 fps, and 640×480; the application loop itself sleeps 0.1 seconds, so practical capture is at most about 10 iterations/s (`sotheby/services/camera_service.py:_load_model`, `_initialize_camera`, `camera_loop`). Historical logs report a 224×224 model input, but the source determines this dynamically.

For inference, BGR is converted to RGB, resized to the model input, and expanded to a batch. Only float32 input is normalized to `[0,1]`; non-float input is passed as the OpenCV uint8 array. The maximum output index and raw output value are used as label/confidence. Inference runs every fifth captured frame only while checking. Labels 0/1 are accepted only at confidence `>= 0.95`; label 2 means “None” (`sotheby/services/camera_service.py:run_inference`, `camera_loop`; `sotheby/models/labels.txt`).

The hardcoded mapping is label 0 = Venus de Milo/Lot 2 and label 1 = The Starry Night/Lot 1, with static artist/story text (`sotheby/services/camera_service.py:ART_INFO`). The root PNGs are not referenced by runtime code.

All artwork status begins `out`. `start_checking()` sets a global checking flag and clears a set of labels detected in this session. The first accepted detection of each artwork toggles it `out→in` or `in→out`, records the relevant Hong Kong time, emits the full table and a story, and then ignores that label for the remainder of the session. Multiple artworks may be toggled in one session. `stop_checking()` only clears the checking flag; it does not validate completeness or persist custody state (`sotheby/services/camera_service.py:start_checking`, `apply_detection`, `stop_checking`, `serialize_art_states`). Starting again while already active clears the suppression set and permits another toggle.

The browser obtains a continuous multipart MJPEG stream from `/video_feed`, retries a failed image up to ten times at two-second intervals, and uses Socket.IO events `start_check`, `done_check`, `status_update`, `phase_update`, `show_story`, and `clear_story` (`sotheby/blueprints/check_bp.py:video_feed`, `register_socketio_handlers`; `sotheby/templates/check.html`). The check workflow and transport session are independent: checking artwork does not start/stop monitoring, create a custody record, or associate artwork with a CSV.

## Persistence, email, and reporting

### CSV

Each transport start creates `transport_logs/transport_YYYYMMDD_HHMMSS_microseconds.csv`. Each sample is flushed immediately. The current schema is:

`timestamp, temperature, humidity, light_intensity, accel_x, accel_y, accel_z, vibration, inclination_deg, latitude, longitude, alert_type, alert_message`

Normal sensor rows leave GPS/alert fields blank. `AlertService.trigger_alert()` appends a sparse alert row to the newest matching CSV by filesystem modification time, even if no transport is active; it does not target `CSVLogger.current_path` and uses a separate lock/file handle (`sotheby/data_access/data.py:CSVLogger`, `append_alert_location`; `sotheby/services/alert_service.py:trigger_alert`). The snapshot's existing CSV has the older nine-column sensor-only schema, demonstrating format drift.

### SQLite

`logistics.db` is a relative working-directory path. `init_db()` creates `gps_history(id,timestamp,latitude,longitude)`, `sensor_events(id,timestamp,event_type,value,latitude,longitude)`, and single-row `active_route(id,name,waypoints,max_deviation_meters)` (`sotheby/data_access/database.py`). SQLite timestamps use `CURRENT_TIMESTAMP`; CSV timestamps use Hong Kong ISO time, and NMEA time is stored only in memory. The included database currently has zero rows in all three tables.

### Email

Email uses `smtplib.SMTP`, STARTTLS, and login to a hardcoded Gmail configuration. Startup starts a daemon connection test, while startup notification sending then occurs synchronously before the web server begins accepting requests. Transport, GPS, security, system-startup, shutdown, and fatal-error message formats are available (`sotheby/email_manager.py:EmailManager`; `sotheby/app.py:create_app`).

Most `EmailManager` methods catch errors and return `False`; `AlertService` ignores the return value and logs that mail was sent, so logs do not prove delivery (`sotheby/email_manager.py:send_email`; `sotheby/services/alert_service.py:trigger_alert`, `send_system_notification`). SMTP calls have no explicit network timeout.

### Reports

`ReportService` loads only the newest CSV by modification time, despite the download filename `transport_logs_combined.csv`; it does not combine files and does not actually exclude older combined exports (`sotheby/services/report_service.py:get_latest_csv_path`; `sotheby/blueprints/report_bp.py:download_csv`). It parses/sorts timestamps, normalizes sensor column names, and calculates acceleration magnitude `sqrt(ax²+ay²+az²)` as `accel_rms` (`sotheby/services/report_service.py:load_transport_data`).

Statistics are min/max/mean/population standard deviation. Status warns if the *mean* exceeds the backend maximum threshold or standard deviation exceeds 5.0. Temperature/humidity lower limits are ignored in report statistics and event extraction. Events are one per row above a maximum threshold; severity is based on percentage above threshold. Logged sparse alert rows are also added as “Info” events (`sotheby/services/report_service.py:compute_basic_stats`, `extract_alert_events`, `classify_severity`). Time-series and correlation plots are generated as base64 PNGs, but the current browser report consumes separate JSON and Chart.js rather than these server-rendered plots.

`/report` unnecessarily generates a complete report before rendering a template that does not use its supplied context; the template then calls `/api/report/data`, generating it again. If the first generation fails, the page itself returns an error and the template's mock-data fallback cannot run. If only the API call fails after the page rendered, the browser displays random mock data and a random report ID (`sotheby/blueprints/report_bp.py:report_page`, `api_report_data`; `sotheby/templates/report.html:loadReport`, `getMockData`).

## HTTP routes and Socket.IO

| Interface | Legacy behavior | Source |
|---|---|---|
| `GET /` | Static dashboard/navigation | `sotheby/app.py:index` |
| `GET /status` | Always says “operational”; service booleans mostly mean object constructed, not hardware/service healthy | `sotheby/app.py:status` |
| `GET /transport` | Monitoring UI | `sotheby/sensor.py:transport_page` |
| `POST /transport/start`, `/stop` | Global sampling/CSV start and stop; route-distance check; broadcasts status | `sotheby/sensor.py:start_transport`, `stop_transport` |
| `GET /transport/data`, `/transport/status` | Recent window/thresholds and duplicated run flags | `sotheby/sensor.py:transport_data`, `transport_status` |
| `GET /gps` and `/api/gps/*` | Map; latest fix, last 2000 GPS points, last 50 persisted events | `sotheby/services/gps/gps_tracking.py` |
| `GET/POST /api/route/*`, `POST /api/data/clear` | Read/set/clear route; destructively clear mission data | `sotheby/services/gps/gps_tracking.py` |
| `GET /check`, `/video_feed` | Artwork UI and MJPEG stream | `sotheby/blueprints/check_bp.py` |
| `GET /report`, `/api/report/data`, `/report/download/csv` | Report page/JSON and newest-file download | `sotheby/blueprints/report_bp.py` |

Socket.IO uses the default namespace and permissive cross-origin configuration. Server events are `sensor_data`, `transport_status`, `alert`, `status_update`, `phase_update`, `show_story`, and `clear_story`. Client commands are `start_check` and `done_check` (`sotheby/app.py:create_app`; sources listed above). There is no authentication, authorization, or per-client session isolation.

## Startup, failure, and shutdown behavior

- Required-import failures—including `smbus2`, Flask/Socket.IO, serial/NMEA, report libraries, and package imports—log critical errors and call `sys.exit(1)` before an app is created (`sotheby/app.py` import blocks). `smbus2` is used but absent from `requirements.txt`.
- GPS serial failure does not stop Flask; the GPS daemon retries forever and APIs report the initial “No Fix” state (`sotheby/services/gps/gps_service.py:run`). A later read failure sleeps and retries reads on the same connection rather than explicitly reopening it.
- I2C bus failure leaves the manager available but emits all-`None` samples once transport starts; there is no mock data despite a misleading “mock data” initialization message. Individual sensors are marked unavailable after read failure and are not reinitialized (`sotheby/sensor.py:init_sensor_manager`, `Sensors.read_all`).
- GPIO initialization failure silently changes the buzzer object to simulation mode, while initialization still returns success and `/status` can report buzzer enabled (`sotheby/hardware/alarm_buzzer.py:_setup_hardware`; `sotheby/hardware/buzzer_integration.py:init_buzzer_system`; `sotheby/app.py:create_app`).
- OpenCV, NumPy, TFLite, missing model, or camera failure is handled inside `CameraService`. Because the service object still exists, `/status` can say camera enabled. The camera loop retries camera index 0 forever; `/video_feed` yields a placeholder/empty frame rather than necessarily returning 503 (`sotheby/services/camera_service.py`).
- Email failure returns false and generally does not stop the app, but synchronous sends can delay startup because no timeout is set (`sotheby/email_manager.py`).
- Missing/invalid CSV makes report routes return 404/500; the browser mock fallback is limited as described above (`sotheby/blueprints/report_bp.py`; `sotheby/templates/report.html`).
- Ctrl+C around `socketio.run()` cleans only the buzzer and camera and attempts a shutdown email. It does not call `SensorManager.stop()`, close the I2C bus/GPS serial connection, stop the GPS thread, or explicitly close an active CSV (`sotheby/app.py` main block). The management script sends `kill`, so graceful Python cleanup is not assured (`sotheby/manage.sh`).
- `start.sh` creates/updates a venv and installs dependencies, but checks for `transport_monitoring.db` while runtime uses `logistics.db`, then imports nonexistent top-level `database`; on a fresh snapshot this initialization command fails before `app.py` (`sotheby/start.sh`; `sotheby/data_access/database.py`). `manage.sh` writes separate `app.log`/`app.pid` files and uses broad `pkill -f` patterns (`sotheby/manage.sh`).

## Security and configuration audit

### Immediate secret/configuration findings

- **Critical:** `sotheby/email_manager.py:DEFAULT_EMAIL_CONFIG` contains a plaintext Gmail app credential plus sender and recipient personal email addresses. Values are intentionally omitted here. Treat the credential as exposed and revoke/rotate it before any repository publication.
- `sotheby/app.py:create_app` hardcodes the Flask secret key, enables Socket.IO CORS for every origin, binds to `0.0.0.0`, and allows the Werkzeug development server in an unsafe mode.
- All state-changing HTTP and Socket.IO operations are unauthenticated and lack CSRF protection. Network clients can start/stop monitoring, toggle check mode, alter/clear routes, and erase GPS/event history (`sotheby/sensor.py`; `sotheby/services/gps/gps_tracking.py`; `sotheby/blueprints/check_bp.py`).
- The GPS page loads OpenStreetMap tiles externally, and templates load Google Fonts externally. Availability and privacy therefore depend on third parties (`sotheby/templates/gps.html`; all main templates).
- Browser templates insert event/story values via `innerHTML`; most values are internally generated today, but unauthenticated APIs and persisted data make this unsafe if inputs become untrusted (`sotheby/templates/gps.html:fetchEvents`; `sotheby/templates/check.html:show_story`; `sotheby/templates/report.html:loadReport`).

### Files that should not enter normal future Git history without deliberate review

- Generated/local state: `.DS_Store`, all `__pycache__/` and `*.pyc`, `sotheby/logs/*.log`, `sotheby/logistics.db`, `sotheby/transport_logs/*.csv`, and runtime-created `sotheby/app.log`, `sotheby/app.pid`, `sotheby/venv/`, rotated logs, or additional databases/CSVs.
- Large/demo evidence: `gps-demo.MOV` (~53 MB) and `project-demo.mov` (~503 MB) should be stored outside ordinary Git or through an intentional large-file/evidence mechanism, after reviewing visual/audio/location metadata and personal information.
- Model/data artifacts requiring provenance and license decisions: `sotheby/models/model.tflite`, `sotheby/models/labels.txt`, `TheStarryNight.png`, and `VenusdeMilo.png`. The model and labels are runtime inputs, not reproducible source; the root PNGs are not referenced by runtime code.
- Vendored third-party assets (`sotheby/static/chart.js`, `leaflet.*`, `socket.io.js`, and Leaflet images) require version/license/provenance review rather than being mistaken for first-party source.
- Existing logs and the generated CSV document an older implementation. They should not be treated as current behavioral truth; `report.log` even contains NUL padding and records functions/messages absent from the current source.

No `.gitignore` is present in the snapshot.

## Known inconsistent, ambiguous, dead, duplicated, or broken behavior

- The accelerometer is disabled in darkness, contrary to using darkness as the assumed secure state while also detecting malicious movement (`Sensors.read_all`).
- `vibration` is not RMS, yet thresholds/report labels call it RMS. With the implemented axis scaling, a threshold of 20 g appears unreachable; the LIS3DSH control setting and conversion comment are also internally questionable (`Sensors._init_lis3dsh`, `read_all`; `ReportService`).
- Backend, transport-template defaults, report mock defaults, and the existing CSV represent different threshold/schema eras.
- Report min-temperature/min-humidity violations are ignored, and mean-based summary status can say OK despite individual violations (`ReportService.compute_basic_stats`, `extract_alert_events`).
- `pick_major_events()` subtracts `value - threshold`; sparse logged alert events use a string value and `None` threshold, so any such event can make report generation fail (`sotheby/services/report_service.py:pick_major_events`, `extract_alert_events`).
- Environment, GPS, timers, and stop/clear actions race over one global buzzer without alert ownership.
- Prolonged violation state leaks across transport sessions; GPS monitoring is not tied to transport sessions; artwork check state is neither persisted nor linked to transport records.
- The camera service health flag means only that the object constructed; missing model/camera can still appear enabled. GPS/email/report health is similarly superficial (`app.status`).
- Email success is logged even when the underlying send returned `False`.
- `/report` computes the same report twice; the advertised combined CSV is only the newest file; older logs describe a no-longer-present combine implementation.
- `static/script.js` duplicates check-page logic but is not referenced by any template. Several `__pycache__` files are stale generated copies.
- `gps.html` calls undefined `showError()` in its Leaflet failure branches; only `showBanner()` exists.
- “Clear route” leaves an empty active-route row; `get_active_route()` therefore returns a route-shaped object instead of no route.
- The GPS event UI marks *any* historical event as an active alert indefinitely until data is cleared; it has no resolved state (`gps.html:fetchEvents`).
- Start/stop route-distance checking uses distance to waypoint points and a hardcoded 500 m, while continuous tracking uses segment cross-track distance and the stored maximum.
- Relative paths and unqualified imports assume the working directory is `sotheby/`; `start.sh` contains a mismatched database name/import.
- No automated tests are present, and no current source execution can prove physical calibration or device compatibility from this snapshot alone.

## Items Requiring Owner Verification

1. Confirm the exact SHT4x variant, GPS receiver, camera, buzzer, and 16×2 LCD/backpack models used in the physical coursework build.
2. Confirm the intended authoritative thresholds—especially temperature max 27 versus 25, light max 6000 versus 150, and vibration moderate 15 versus 10—and whether boundary equality is meant to be normal or abnormal.
3. Confirm the LIS3DSH configured full-scale range, axis calibration, physical orientation, and the intended definition/unit of “vibration” (gravity-deviation, acceleration magnitude, RMS over a time window, or another measure).
4. Confirm whether accelerometer readings were intentionally disabled in darkness or whether that coupling is an accidental legacy bug.
5. Confirm whether route deviation should be active only during a transport session and whether distance should be measured to route segments, waypoints, or both at start/stop.
6. Confirm the intended custody workflow: which detection means check-in versus check-out, whether all artworks must be scanned, and how a check session should relate to a transport session/report.
7. Confirm the TFLite model's training provenance, expected input dtype/quantization, class ordering, confidence calibration, and whether label 0/1 mapping was physically validated.
8. Confirm the intended time basis across GPS/NMEA, SQLite, CSV, email, and reports, and whether all displayed/persisted times should be Hong Kong time.
9. Confirm which demo videos, artwork images, model/labels, and sample data are permitted to publish and whether any contain personal, location, copyrighted, or third-party material.
10. Confirm whether the observed older report behavior (combined CSV generation recorded in `report.log`) or the current source behavior (latest CSV only) is the intended coursework reference.
