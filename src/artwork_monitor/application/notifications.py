"""Build deterministic notifications from existing violation results."""

from __future__ import annotations

from collections.abc import Iterable

from artwork_monitor.domain import (
    NotificationKind,
    NotificationMessage,
    Violation,
    format_hong_kong_timestamp,
)


def notification_messages(
    session_id: str,
    *,
    immediate_violations: Iterable[Violation],
    prolonged_violations: Iterable[Violation],
) -> tuple[NotificationMessage, ...]:
    """Return immediate messages first, then one-shot prolonged messages."""

    immediate = tuple(
        _message(session_id, NotificationKind.IMMEDIATE, violation)
        for violation in immediate_violations
    )
    prolonged = tuple(
        _message(session_id, NotificationKind.PROLONGED, violation)
        for violation in prolonged_violations
    )
    return immediate + prolonged


def _message(
    session_id: str, kind: NotificationKind, violation: Violation
) -> NotificationMessage:
    condition = violation.condition.value
    summary = (
        f"{kind.value.capitalize()} {condition}: observed {violation.observed_value:g} "
        f"{violation.unit} against threshold {violation.threshold_value:g} {violation.unit}."
    )
    return NotificationMessage(
        session_id=session_id,
        kind=kind,
        condition=condition,
        summary=summary,
        observed_value=violation.observed_value,
        threshold_value=violation.threshold_value,
        unit=violation.unit,
        occurred_at=format_hong_kong_timestamp(violation.occurred_at),
    )
