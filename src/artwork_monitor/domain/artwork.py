"""Artwork identity, detection interpretation, and custody-state values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from numbers import Real


class ArtworkStatus(str, Enum):
    """Legacy in-memory artwork status."""

    IN = "in"
    OUT = "out"


@dataclass(frozen=True, slots=True)
class ArtworkIdentity:
    """A documented artwork class from the legacy labels file."""

    label_index: int
    name: str
    lot: str
    artist: str
    description: str


@dataclass(frozen=True, slots=True)
class ArtworkState:
    """The in-memory legacy status for one artwork."""

    identity: ArtworkIdentity
    status: ArtworkStatus = ArtworkStatus.OUT
    time_in: datetime | None = None
    time_out: datetime | None = None


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Raw label and confidence returned by an inference engine."""

    label_index: int
    confidence: float

    def __post_init__(self) -> None:
        if isinstance(self.label_index, bool) or not isinstance(self.label_index, int):
            raise ValueError("label_index must be an integer")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, Real):
            raise ValueError("confidence must be numeric")
        if not math.isfinite(self.confidence):
            raise ValueError("confidence must be finite")


@dataclass(frozen=True, slots=True)
class ArtworkDetection:
    """A legacy-recognized artwork result accepted for state application."""

    identity: ArtworkIdentity
    confidence: float


_LEGACY_IDENTITIES = {
    0: ArtworkIdentity(
        label_index=0,
        name="Venus de Milo",
        lot="Lot 2",
        artist="Alexandros of Antioch",
        description=(
            "Sculpted from Parian marble circa 100 BCE, the Venus de Milo is a "
            "paradigmatic example of Hellenistic statuary attributed to Alexandros "
            "of Antioch."
        ),
    ),
    1: ArtworkIdentity(
        label_index=1,
        name="The Starry Night",
        lot="Lot 1",
        artist="Vincent van Gogh",
        description=(
            "Executed during Van Gogh's convalescence at Saint-Rémy, The Starry "
            "Night defines the Post-Impressionist canon."
        ),
    ),
}


def legacy_artworks() -> dict[int, ArtworkState]:
    """Return fresh all-``out`` state for each documented legacy artwork."""

    return {label: ArtworkState(identity) for label, identity in _LEGACY_IDENTITIES.items()}


def interpret_detection(result: InferenceResult | None) -> ArtworkDetection | None:
    """Accept only the exact documented labels and confidence threshold."""

    if result is None or result.confidence < 0.95:
        return None
    identity = _LEGACY_IDENTITIES.get(result.label_index)
    if identity is None:
        return None
    return ArtworkDetection(identity=identity, confidence=float(result.confidence))
