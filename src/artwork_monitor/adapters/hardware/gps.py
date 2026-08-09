"""Synchronous optional serial/NMEA GPS input."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from artwork_monitor.domain import GPSFix, GPSFixStatus, HONG_KONG


class SerialNmeaGPSFixSource:
    """Pull one RMC observation at a time from an instance-owned serial handle."""

    def __init__(
        self,
        *,
        port: str = "/dev/serial0",
        baudrate: int = 9600,
        timeout: float = 5.0,
        serial_factory: Callable[..., Any] | None = None,
        parser: Callable[[str], Any] | None = None,
    ) -> None:
        self._port, self._baudrate, self._timeout = port, baudrate, timeout
        self._serial_factory, self._parser, self._serial = serial_factory, parser, None

    def next_fix(self) -> GPSFix | None:
        """Read and interpret one line without retrying or background work."""
        raw_line = self._connection().readline()
        if not raw_line:
            return None
        line = (
            raw_line.decode("ascii", errors="ignore").strip()
            if isinstance(raw_line, bytes)
            else str(raw_line).strip()
        )
        if not _is_rmc(line):
            return None
        try:
            message = self._nmea_parser()(line)
            observed_at = _observation_time(message)
        except Exception:
            return None
        status = getattr(message, "status", None)
        if status == "A":
            try:
                return GPSFix(
                    observed_at,
                    GPSFixStatus.FIX,
                    float(message.latitude),
                    float(message.longitude),
                )
            except (TypeError, ValueError):
                return None
        if status == "V":
            return GPSFix.no_fix(observed_at)
        return None

    def reset(self) -> None:
        """Release the serial handle so a future pull opens a new one."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def _connection(self) -> Any:
        if self._serial is None:
            factory = self._serial_factory
            if factory is None:
                from serial import Serial

                factory = Serial
            self._serial = factory(
                port=self._port, baudrate=self._baudrate, timeout=self._timeout
            )
        return self._serial

    def _nmea_parser(self) -> Callable[[str], Any]:
        if self._parser is not None:
            return self._parser
        from pynmea2 import parse

        return parse


def _is_rmc(line: str) -> bool:
    return line.startswith("$") and len(line) >= 6 and line[3:6] == "RMC"


def _observation_time(message: Any) -> datetime:
    return datetime.combine(
        message.datestamp, message.timestamp, tzinfo=timezone.utc
    ).astimezone(HONG_KONG)
