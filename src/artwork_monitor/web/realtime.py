"""Socket.IO event publication for explicit web actions only."""

from __future__ import annotations

from typing import Any


class RealtimeEventAdapter:
    """Publish pre-serialized interface events without owning any workflow state."""

    def __init__(self, socketio: Any) -> None:
        self._socketio = socketio

    def publish(self, event: str, payload: dict[str, Any]) -> None:
        self._socketio.emit(event, payload)
