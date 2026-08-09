"""Optional instance-scoped GPIO alarm output."""

from __future__ import annotations

from typing import Any

from artwork_monitor.ports.alarms import AlarmSource


class GpioAlarmOutput:
    """Set a GPIO output while one or more instance-owned sources are active."""

    def __init__(self, *, gpio: Any | None = None, gpio_pin: int = 18) -> None:
        self._gpio, self._gpio_pin, self._initialized = gpio, gpio_pin, False
        self._active_sources: set[AlarmSource] = set()

    def set_active(self, source: AlarmSource, active: bool) -> None:
        was_active = bool(self._active_sources)
        if active:
            self._active_sources.add(source)
        else:
            self._active_sources.discard(source)
        if was_active != bool(self._active_sources):
            self._write(bool(self._active_sources))

    def reset(self) -> None:
        self._active_sources.clear()
        if self._initialized:
            self._gpio.output(self._gpio_pin, self._gpio.LOW)

    def _write(self, active: bool) -> None:
        gpio = self._ensure_gpio()
        gpio.output(self._gpio_pin, gpio.HIGH if active else gpio.LOW)

    def _ensure_gpio(self) -> Any:
        if self._gpio is None:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
        if not self._initialized:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setup(self._gpio_pin, self._gpio.OUT)
            self._initialized = True
        return self._gpio
