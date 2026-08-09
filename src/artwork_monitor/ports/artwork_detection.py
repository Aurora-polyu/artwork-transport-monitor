"""Clean input contracts for artwork camera and inference adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from artwork_monitor.domain import InferenceResult


@dataclass(frozen=True, slots=True)
class CameraFrame:
    """An opaque captured frame identified deterministically by its source."""

    frame_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, str) or not self.frame_id:
            raise ValueError("frame_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class PreparedImage:
    """An opaque preprocessed frame ready for a detector."""

    frame_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, str) or not self.frame_id:
            raise ValueError("frame_id must be a non-empty string")


class CameraSource(Protocol):
    """Supply captured frames one at a time."""

    def next_frame(self) -> CameraFrame | None:
        """Return the next frame, or ``None`` when the source is exhausted."""


class ImagePreprocessor(Protocol):
    """Convert one captured frame into detector-ready input."""

    def prepare(self, frame: CameraFrame) -> PreparedImage:
        """Prepare ``frame`` without deciding its identity."""


class Detector(Protocol):
    """Run inference on a prepared image."""

    def infer(self, image: PreparedImage) -> InferenceResult | None:
        """Return raw inference data, or no detection."""
