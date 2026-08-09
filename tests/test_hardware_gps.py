from datetime import date, time
from types import SimpleNamespace
import threading
import unittest

from artwork_monitor.adapters.hardware.gps import SerialNmeaGPSFixSource
from artwork_monitor.domain import GPSFixStatus


class _Serial:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines
        self.closed = False

    def readline(self) -> bytes:
        return self.lines.pop(0) if self.lines else b""

    def close(self) -> None:
        self.closed = True


def _rmc(status: str = "A") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        latitude="22.302",
        longitude="114.177",
        datestamp=date(2026, 8, 9),
        timestamp=time(4, 30, 0),
    )


class SerialNmeaGPSFixSourceTests(unittest.TestCase):
    def test_construction_does_not_open_serial_or_start_a_thread(self) -> None:
        calls: list[dict[str, object]] = []

        def factory(**kwargs):
            calls.append(kwargs)
            return _Serial([])

        before = threading.active_count()
        SerialNmeaGPSFixSource(serial_factory=factory, parser=lambda _: _rmc())

        self.assertEqual(calls, [])
        self.assertEqual(threading.active_count(), before)

    def test_active_rmc_uses_defaults_and_converts_timestamp_to_hong_kong(self) -> None:
        calls: list[dict[str, object]] = []
        serial = _Serial([b"$GPRMC,example\r\n"])

        def factory(**kwargs):
            calls.append(kwargs)
            return serial

        source = SerialNmeaGPSFixSource(serial_factory=factory, parser=lambda _: _rmc("A"))
        fix = source.next_fix()

        self.assertEqual(calls, [{"port": "/dev/serial0", "baudrate": 9600, "timeout": 5.0}])
        assert fix is not None
        self.assertEqual(fix.status, GPSFixStatus.FIX)
        self.assertEqual((fix.latitude, fix.longitude), (22.302, 114.177))
        self.assertEqual(fix.timestamp.isoformat(), "2026-08-09T12:30:00+08:00")

    def test_inactive_rmc_is_explicit_no_fix(self) -> None:
        source = SerialNmeaGPSFixSource(
            serial_factory=lambda **_: _Serial([b"$GNRMC,example\r\n"]),
            parser=lambda _: _rmc("V"),
        )

        fix = source.next_fix()

        assert fix is not None
        self.assertEqual(fix.status, GPSFixStatus.NO_FIX)
        self.assertIsNone(fix.latitude)
        self.assertEqual(fix.timestamp.isoformat(), "2026-08-09T12:30:00+08:00")

    def test_unknown_rmc_status_is_not_reported_as_no_fix(self) -> None:
        source = SerialNmeaGPSFixSource(
            serial_factory=lambda **_: _Serial([b"$GNRMC,example\r\n"]),
            parser=lambda _: _rmc(""),
        )

        self.assertIsNone(source.next_fix())

    def test_non_rmc_malformed_and_empty_input_return_no_new_observation(self) -> None:
        parser_calls: list[str] = []
        source = SerialNmeaGPSFixSource(
            serial_factory=lambda **_: _Serial([b"$GPGGA,example\r\n", b"$GPRMC,bad\r\n", b""]),
            parser=lambda line: parser_calls.append(line) or (_ for _ in ()).throw(ValueError("bad RMC")),
        )

        self.assertIsNone(source.next_fix())
        self.assertIsNone(source.next_fix())
        self.assertIsNone(source.next_fix())
        self.assertEqual(parser_calls, ["$GPRMC,bad"])

    def test_reset_closes_instance_owned_serial_handle(self) -> None:
        serial = _Serial([b"$GPRMC,example\r\n"])
        source = SerialNmeaGPSFixSource(serial_factory=lambda **_: serial, parser=lambda _: _rmc())

        source.next_fix()
        source.reset()

        self.assertTrue(serial.closed)
