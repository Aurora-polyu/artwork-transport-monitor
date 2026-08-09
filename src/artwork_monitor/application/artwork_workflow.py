"""Synchronous legacy-compatible artwork detection and state workflow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from artwork_monitor.domain import (
    ArtworkDetection,
    ArtworkState,
    ArtworkStatus,
    HONG_KONG,
    interpret_detection,
    legacy_artworks,
)
from artwork_monitor.ports import CameraSource, Detector, ImagePreprocessor


@dataclass(frozen=True, slots=True)
class ArtworkTransition:
    """One accepted first-in-session detection changing an artwork state."""

    label_index: int
    status: ArtworkStatus
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ArtworkWorkflowStep:
    """The observable result of processing one captured frame."""

    frame_id: str
    inference_attempted: bool
    detection: ArtworkDetection | None
    transition: ArtworkTransition | None


class ArtworkWorkflow:
    """Apply the legacy artwork state rules without camera or ML dependencies."""

    def __init__(
        self,
        *,
        camera_source: CameraSource,
        preprocessor: ImagePreprocessor,
        detector: Detector,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._camera_source = camera_source
        self._preprocessor = preprocessor
        self._detector = detector
        self._clock = clock or (lambda: datetime.now(HONG_KONG))
        self._states = legacy_artworks()
        self._checking = False
        self._captured_frame_count = 0
        self._detected_in_session: set[int] = set()

    @property
    def checking(self) -> bool:
        """Whether detection interpretation is active."""

        return self._checking

    def start(self) -> None:
        """Start a session and clear only its duplicate-detection suppression."""

        self._checking = True
        self._detected_in_session.clear()

    def stop(self) -> None:
        """Stop checking while retaining all artwork state."""

        self._checking = False

    def states(self) -> dict[int, ArtworkState]:
        """Return a snapshot of in-memory artwork state."""

        return dict(self._states)

    def process_next_frame(self) -> ArtworkWorkflowStep | None:
        """Capture and, when due and active, process exactly one frame."""

        frame = self._camera_source.next_frame()
        if frame is None:
            return None

        self._captured_frame_count += 1
        if not self._checking or self._captured_frame_count % 5:
            return ArtworkWorkflowStep(
                frame_id=frame.frame_id,
                inference_attempted=False,
                detection=None,
                transition=None,
            )

        result = self._detector.infer(self._preprocessor.prepare(frame))
        detection = interpret_detection(result)
        return ArtworkWorkflowStep(
            frame_id=frame.frame_id,
            inference_attempted=True,
            detection=detection,
            transition=self._apply_detection(detection),
        )

    def run_to_exhaustion(self) -> tuple[ArtworkWorkflowStep, ...]:
        """Process scripted frames synchronously until the source is exhausted."""

        steps: list[ArtworkWorkflowStep] = []
        while (step := self.process_next_frame()) is not None:
            steps.append(step)
        return tuple(steps)

    def _apply_detection(self, detection: ArtworkDetection | None) -> ArtworkTransition | None:
        if detection is None:
            return None
        label_index = detection.identity.label_index
        if label_index in self._detected_in_session:
            return None

        self._detected_in_session.add(label_index)
        state = self._states[label_index]
        occurred_at = self._clock()
        if state.status is ArtworkStatus.OUT:
            status = ArtworkStatus.IN
            updated_state = replace(state, status=status, time_in=occurred_at)
        else:
            status = ArtworkStatus.OUT
            updated_state = replace(state, status=status, time_out=occurred_at)
        self._states[label_index] = updated_state
        return ArtworkTransition(label_index=label_index, status=status, occurred_at=occurred_at)
