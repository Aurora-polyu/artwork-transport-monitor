"""In-memory notification collection for deterministic tests and demos."""

from __future__ import annotations

from dataclasses import dataclass, field

from artwork_monitor.domain import NotificationMessage


@dataclass(slots=True)
class InMemoryNotificationDispatcher:
    """Record dispatches in call order without performing any I/O."""

    messages: list[NotificationMessage] = field(default_factory=list)

    def dispatch(self, message: NotificationMessage) -> None:
        self.messages.append(message)
