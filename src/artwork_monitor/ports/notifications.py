"""Delivery contract for transport-monitoring notifications."""

from __future__ import annotations

from typing import Protocol

from artwork_monitor.domain import NotificationMessage


class NotificationDispatcher(Protocol):
    """Deliver one already-formed notification without changing its meaning."""

    def dispatch(self, message: NotificationMessage) -> None: ...
