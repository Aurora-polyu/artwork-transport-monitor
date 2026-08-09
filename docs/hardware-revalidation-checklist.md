# Hardware Revalidation Checklist

Use this checklist only after the deterministic software demo and its tests
pass. Record device model, wiring/pin mapping, software revision, operator,
date, observed result, and retained evidence for every item. A checked item is
not implied by the clean software rebuild.

## Bring-up and lifecycle

- [ ] Identify the Raspberry Pi model, OS image, power supply, and installed
  dependency versions; boot repeatedly without application errors.
- [ ] Confirm explicit start, stop, and shutdown leave no sensor/GPS/camera
  process, open file, thread, or GPIO output active.
- [ ] Confirm restart creates a new session without leaking prior filters,
  alerts, locations, or persisted records.

## Environmental sensing

- [ ] Verify the installed temperature/humidity, light, and accelerometer
  models, I2C addresses, units, and read cadence against the hardware
  inventory.
- [ ] Compare stable readings with trusted references; document calibration,
  tolerance, missing-read behavior, and the approved thresholds.
- [ ] Exercise normal, temperature, humidity, light, and motion/gravity cases
  safely; confirm immediate versus prolonged condition behavior separately.

## GPS, camera, and alarm

- [ ] Confirm serial GPS port, baud rate, active-fix parsing, no-fix handling,
  timestamps, and retained coordinates during a controlled route.
- [ ] Confirm the camera opens, the intended TFLite model/labels load, and
  recognition behavior is evaluated with authorised test artwork only.
- [ ] Confirm buzzer wiring, electrical safety, start/stop behavior, and alert
  audibility without leaving an alarm energised after shutdown.

## Persistence and real alerts

- [ ] Verify one physical transport session produces only its own SQLite rows,
  CSV export, report, timestamps, and GPS/violation records after restart.
- [ ] Validate disk-full, interrupted-write, sensor-loss, GPS-loss, and camera
  failure handling without fabricating normal data.
- [ ] Test real alert delivery only with approved recipients and credentials;
  record recipient policy, rate limits, authentication, failure handling, and
  evidence. Do not use the in-memory demo dispatcher as evidence of delivery.

## Sign-off boundary

- [ ] Attach the recorded results and unresolved anomalies to the release or
  demo record.
- [ ] Do not claim physical monitoring, calibrated vibration/damage detection,
  route compliance, camera accuracy, or real alert delivery until the relevant
  items above have passed and been reviewed.
