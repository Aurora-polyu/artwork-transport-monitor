# Legacy Hardware Inventory

This inventory records what the source identifies. “Not identifiable” means the model cannot be determined reliably from the snapshot and is listed for owner verification in `legacy-system-spec.md`.

## Host platform and buses

| Item | Identified configuration | Legacy source/behavior |
|---|---|---|
| Host | Raspberry Pi-family Linux host; scripts mention Raspberry Pi and `raspi-config` | `sotheby/requirements.txt`; `sotheby/services/gps/gps_service.py:connect_serial` |
| I2C | `/dev/i2c-1` through `smbus2.SMBus(1)` | `sotheby/sensor.py:I2C_BUS_ID`, `SensorManager.__init__` |
| UART/serial | `/dev/serial0`, 9600 baud, 5 s read timeout | `sotheby/services/gps/gps_service.py:GPS_SERIAL_PORT`, `GPS_BAUD_RATE`, `connect_serial` |
| GPIO numbering | BCM numbering | `sotheby/hardware/alarm_buzzer.py:BuzzerAlarm._setup_hardware` |
| Camera | OpenCV `VideoCapture(0)`; requests 640×480, 30 fps, buffer size 1 | `sotheby/services/camera_service.py:_initialize_camera` |

## Devices and pin/address map

| Function | Device/model identifiable from code | Interface | Address/pin | Initialization/configuration |
|---|---|---|---|---|
| Temperature/humidity | Sensirion SHT4x family; exact variant not identifiable | I2C bus 1 | `0x44` | Soft reset `0x94`; serial command `0x89`; measurement commands high `0xFD`, medium `0xF6`, low `0xE0` (`sotheby/sensor.py:Sensors._init_sht4x`, `read_all`) |
| Ambient light | Vishay VEML7700 | I2C bus 1 | `0x10` | Writes configuration register `0x00` bytes `[0x00,0x00]`; reads ALS register `0x04`; conversion 0.2688 lux/count (`sotheby/sensor.py:Sensors._init_veml7700`, `read_all`) |
| Acceleration | ST LIS3DSH | I2C bus 1 | `0x19` | CTRL4 (`0x20`) = `0x67`; CTRL5 (`0x24`) = `0x08`; six-byte read begins at `0x28 | 0x80` (`sotheby/sensor.py:Sensors._init_lis3dsh`, `read_all`) |
| Display | 16×2 HD44780-compatible LCD via PCF8574-style I2C backpack; exact modules not identifiable | I2C bus 1, 4-bit LCD protocol | `0x27` | 16 columns, 2 lines; backlight bit `0x08`, enable `0x04`, RS `0x01`; standard 4-bit init (`sotheby/hardware/display.py:I2CDisplay`) |
| Audible alarm | GPIO-driven buzzer; active/passive and exact model not identifiable | Raspberry Pi GPIO | BCM GPIO18, physical pin 12 | Initial LOW; 1 kHz PWM, 50% duty, 0.3 s tone, ~0.5 s inter-beep interval; pulse fallback (`sotheby/hardware/buzzer_integration.py`; `sotheby/hardware/alarm_buzzer.py`) |
| GPS | NMEA-compatible serial GPS receiver; exact model/chipset not identifiable | UART | `/dev/serial0`, 9600 baud | Parses active RMC sentences only via `pynmea2` (`sotheby/services/gps/gps_service.py:GPSService.run`) |
| Camera | USB/CSI camera exposed as OpenCV index 0; exact model not identifiable | Linux/OpenCV video backend | index `0` | One test frame required; then 640×480/30 fps requests (`sotheby/services/camera_service.py:_initialize_camera`) |

## Sensor outputs and calculations

| Output field | Source | Implemented unit/calculation | Filtering/availability |
|---|---|---|---|
| `temperature` | SHT4x raw word | °C; `-45 + 175×raw/65535` | EWMA α=0.1; unavailable after persistent read failure |
| `humidity` | SHT4x raw word | % RH; `-6 + 125×raw/65535`, clamped 0–100 | EWMA α=0.1 |
| `light_intensity` | VEML7700 ALS raw word | lux; raw×0.2688 | EWMA α=0.3 |
| `accel_x/y/z` | LIS3DSH signed words | code labels g; raw×`8/65536` | No filter; read only if lux > 0.1 |
| `vibration` | Derived from axes | `abs(norm(ax,ay,az)-1.0)`, labelled g | Values <0.02 forced to 0; not actually an RMS window |
| `inclination_deg` | Derived from axes | `degrees(acos(az / norm))`, 0–180° | No filter; zeroed with axes when lux ≤0.1 |
| `vibration_status` | Derived manager field | `excessive` at vibration ≥20, otherwise `normal` | Not included in CSV schema |

Source: `sotheby/sensor.py:Sensors.read_all`, `SensorFilter`, `SensorManager._run_loop`.

## Software dependencies and interfaces

| Library/interface | Role | Legacy status |
|---|---|---|
| `smbus2`, `i2c_msg` | I2C bus/device access | Imported directly by `sensor.py` but missing from `requirements.txt`; its absence prevents app import |
| `RPi.GPIO` | GPIO and PWM buzzer control | Pinned as 0.7.1; imported lazily; hardware failure falls back to simulation |
| `pyserial` 3.5 | GPS serial I/O | Required at import; no GPS mock/fallback provider |
| `pynmea2` 1.19.0 | NMEA RMC parsing | Required at import |
| `opencv-python` 4.8.1.78 | Camera capture, resize/color conversion, JPEG/MJPEG encoding | Import failure disables camera features without aborting `CameraService` import |
| `numpy` 1.24.3 | Frames, model tensors, report calculations | Camera treats missing NumPy as graceful, but report service imports it unconditionally |
| `tflite-runtime` 2.13.0 | TFLite interpreter | Import/model failure disables inference; model service object still exists |
| Flask 2.3.3 / Flask-SocketIO 5.3.6 | HTTP templates/APIs and realtime events | Required; server binds all interfaces on port 5000 |
| SQLite (`sqlite3`) | GPS/event/route persistence | Standard library; relative file `logistics.db` |
| pandas 2.0.3 / matplotlib 3.7.2 | Report loading/statistics/plots | Required during service-module import; Matplotlib uses `Agg` |
| `smtplib` / MIME modules | STARTTLS email | Standard library; `secure-smtplib` is listed but code does not use it |
| Chart.js | Browser charts | Vendored minified `sotheby/static/chart.js` |
| Leaflet 1.9.4 | GPS map | Vendored JS/CSS/images; tiles still require OpenStreetMap network access |
| Socket.IO client 4.5.3 | Browser realtime connection | Vendored `sotheby/static/socket.io.js` |

`SQLAlchemy`, `python-dateutil`, and `os` in `email_manager.py` are not required by the observed active paths (SQLite uses `sqlite3`; Hong Kong timezone uses the standard library). Source: `sotheby/requirements.txt` and module imports.

## Hardware loss/failure behavior

- Whole I2C bus unavailable: sensor manager still exists, CSV/session can start, and each sample contains `None`; LCD is absent. There is no generated mock reading (`sotheby/sensor.py:SensorManager.__init__`, `_read_all_sensors`).
- Individual SHT4x/VEML7700/LIS3DSH read failure: its `*_ok` flag becomes false and no reconnect/reinitialization is attempted (`sotheby/sensor.py:Sensors.read_all`).
- LCD not at `0x27` or later write fails: `available=False`; monitoring continues (`sotheby/hardware/display.py:I2CDisplay`).
- GPIO failure: buzzer switches to console simulation, but higher layers still treat initialization as successful (`sotheby/hardware/alarm_buzzer.py:_setup_hardware`; `sotheby/app.py:create_app`).
- GPS unavailable: a daemon reconnect loop continues every five seconds; web/server startup continues (`sotheby/services/gps/gps_service.py:run`).
- Camera unavailable: reconnect is attempted about once per second forever and the MJPEG generator serves a placeholder/empty frame (`sotheby/services/camera_service.py:camera_loop`, `generate_frames`).
- TFLite/model unavailable: every inference returns label 2 with confidence 0; streaming can continue (`sotheby/services/camera_service.py:_load_model`, `run_inference`).

## Calibration and configuration cautions

- The code's “±8 g” comment and `8/65536` conversion do not self-consistently describe a signed full-scale span; physical validation is required.
- A 20 g “vibration” threshold is inconsistent with the implemented gravity-deviation metric and configured axis scale and appears unreachable.
- Light gates all accelerometer output, so a dark enclosure reports zero motion rather than measuring it.
- SHT4x CRC bytes are not checked.
- No sensor serial number, calibration coefficient, camera identity, GPS model, or buzzer/display exact part number is persisted.
