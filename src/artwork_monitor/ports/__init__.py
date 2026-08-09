"""Minimal input-port contracts for future source adapters."""

from .artwork_detection import (
    CameraFrame,
    CameraSource,
    Detector,
    ImagePreprocessor,
    PreparedImage,
)
from .alarms import AlarmOutput, AlarmSource
from .gps import GPSFixSource
from .notifications import NotificationDispatcher
from .persistence import TransportSessionExporter, TransportSessionRepository
from .sensors import SensorSource

__all__ = [
    "CameraFrame",
    "CameraSource",
    "Detector",
    "AlarmOutput",
    "AlarmSource",
    "GPSFixSource",
    "ImagePreprocessor",
    "NotificationDispatcher",
    "PreparedImage",
    "SensorSource",
    "TransportSessionExporter",
    "TransportSessionRepository",
]
