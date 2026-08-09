import unittest
import sys

from artwork_monitor.adapters.hardware.alarms import GpioAlarmOutput
from artwork_monitor.ports import AlarmSource


class _Gpio:
    BCM = "BCM"
    OUT = "OUT"
    HIGH = "HIGH"
    LOW = "LOW"

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def setmode(self, value: object) -> None:
        self.calls.append(("setmode", value))

    def setup(self, pin: int, mode: object) -> None:
        self.calls.append(("setup", pin, mode))

    def output(self, pin: int, value: object) -> None:
        self.calls.append(("output", pin, value))


class GpioAlarmOutputTests(unittest.TestCase):
    def test_adapter_import_does_not_load_gpio_hardware(self) -> None:
        self.assertNotIn("RPi", sys.modules)
        self.assertNotIn("RPi.GPIO", sys.modules)

    def test_owner_activation_is_idempotent_and_partial_clear_keeps_hardware_active(
        self,
    ) -> None:
        gpio = _Gpio()
        output = GpioAlarmOutput(gpio=gpio)

        output.set_active(AlarmSource.TRANSPORT_MONITORING, True)
        first_calls = list(gpio.calls)
        output.set_active(AlarmSource.TRANSPORT_MONITORING, True)
        output.set_active(AlarmSource.GPS_ROUTE, True)
        output.set_active(AlarmSource.TRANSPORT_MONITORING, False)

        self.assertEqual(gpio.calls, first_calls)
        self.assertNotIn(("output", 18, gpio.LOW), gpio.calls)

    def test_clearing_final_owner_and_reset_deactivate_hardware(self) -> None:
        gpio = _Gpio()
        output = GpioAlarmOutput(gpio=gpio)

        output.set_active(AlarmSource.TRANSPORT_MONITORING, True)
        output.set_active(AlarmSource.GPS_ROUTE, True)
        output.set_active(AlarmSource.TRANSPORT_MONITORING, False)
        output.set_active(AlarmSource.GPS_ROUTE, False)
        output.set_active(AlarmSource.TRANSPORT_MONITORING, True)
        output.reset()

        self.assertEqual(
            [call for call in gpio.calls if call[0] == "output"],
            [
                ("output", 18, gpio.HIGH),
                ("output", 18, gpio.LOW),
                ("output", 18, gpio.HIGH),
                ("output", 18, gpio.LOW),
            ],
        )
