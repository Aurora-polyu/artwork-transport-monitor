"""Optional physical adapters with lazy hardware access."""

from .alarms import GpioAlarmOutput
from .gps import SerialNmeaGPSFixSource

__all__ = ["GpioAlarmOutput", "SerialNmeaGPSFixSource"]
