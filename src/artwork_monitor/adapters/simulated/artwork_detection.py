"""Finite software-only camera and detector adapters for artwork workflows."""

from __future__ import annotations

from collections.abc import Iterable

from artwork_monitor.domain import InferenceResult
from artwork_monitor.ports import CameraFrame, PreparedImage


class SequenceCameraSource:
    """Return a finite scripted sequence of opaque camera frames."""

    def __init__(self, frames: Iterable[CameraFrame]) -> None:
        self._frames = tuple(frames)
        self._position = 0

    def next_frame(self) -> CameraFrame | None:
        if self._position >= len(self._frames):
            return None
        frame = self._frames[self._position]
        self._position += 1
        return frame

    def reset(self) -> None:
        self._position = 0


class PassthroughImagePreprocessor:
    """Retain scripted frame identity without requiring an image library."""

    def prepare(self, frame: CameraFrame) -> PreparedImage:
        return PreparedImage(frame.frame_id)


class SequenceDetector:
    """Return finite scripted raw inference results, then no detection."""

    def __init__(self, results: Iterable[InferenceResult | None]) -> None:
        self._results = tuple(results)
        self._position = 0

    def infer(self, image: PreparedImage) -> InferenceResult | None:
        del image
        if self._position >= len(self._results):
            return None
        result = self._results[self._position]
        self._position += 1
        return result

    def reset(self) -> None:
        self._position = 0
