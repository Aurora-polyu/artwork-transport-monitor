"""Hardware-neutral GPS input contract."""

from __future__ import annotations

from typing import Protocol

from artwork_monitor.domain import GPSFix


class GPSFixSource(Protocol):
    """Provide the next GPS state, or ``None`` when the scripted source ends."""

    def next_fix(self) -> GPSFix | None: ...

    def reset(self) -> None: ...
