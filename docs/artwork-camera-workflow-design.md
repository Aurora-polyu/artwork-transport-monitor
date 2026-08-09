# Artwork Camera and Detection Workflow

Task 9 reconstructs the legacy artwork-identification behavior as a synchronous,
software-only workflow. It does not add Flask, Socket.IO, streaming, physical
camera support, model training, or changes to the transport monitoring,
persistence, notification, and reporting workflow.

## Preserved behavior

- The documented identities are label `0`, Venus de Milo / Lot 2, and label
  `1`, The Starry Night / Lot 1. Their legacy artist and story metadata stays
  attached to the identity.
- Each artwork starts `out`. An accepted detection toggles its stored state
  `out` ↔ `in`; a scan does not itself mean check-in or check-out.
- A transition records Hong Kong `time_in` or `time_out`.
- Only the first accepted detection of an artwork within a detection session
  changes state. Starting a session clears duplicate suppression, including if
  already active; stopping only disables checking.
- Inference is attempted on every fifth captured frame while checking.
- Only labels `0` or `1` at confidence `>= 0.95` are accepted. Label `2`
  (None), unknown labels, no detection, and lower confidence do not change
  artwork state.
- Artwork state is in-memory and independent of transport sessions, CSV,
  reports, and persistence.

## Boundaries

The workflow is pull-based: `CameraSource` captures a `CameraFrame`,
`ImagePreprocessor` creates a `PreparedImage`, `Detector` returns an
`InferenceResult`, pure interpretation accepts or rejects the result, and
`ArtworkWorkflow` applies the state transition. The core/domain/application
layers import no PiCamera, OpenCV, TensorFlow Lite, Raspberry Pi package,
socket, or thread API.

`SequenceCameraSource`, `PassthroughImagePreprocessor`, and `SequenceDetector`
are finite deterministic adapters for tests and laptop demos. They use no
network and start no background threads.

## Future physical/model adapter

The clean branch intentionally has no runtime TFLite model or label artifact.
A future optional adapter must implement the three ports above and own the
legacy BGR-to-RGB conversion, resize to the model input, batch expansion, and
float32-only `[0,1]` normalization. It must load an explicitly supplied model
path and remain isolated from normal core imports.

Physical camera behavior, model input quantization, class ordering, and
confidence calibration still require later physical/model validation.
