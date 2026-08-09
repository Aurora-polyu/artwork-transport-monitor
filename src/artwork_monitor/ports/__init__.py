"""Minimal input-port contracts for future source adapters."""

from .artwork_detection import CameraFrame, CameraSource, Detector, ImagePreprocessor, PreparedImage
from .gps import GPSFixSource
from .notifications import NotificationDispatcher
from .persistence import TransportSessionExporter, TransportSessionRepository
from .sensors import SensorSource

__all__ = [
    "CameraFrame",
    "CameraSource",
    "Detector",
    "GPSFixSource",
    "ImagePreprocessor",
    "NotificationDispatcher",
    "PreparedImage",
    "SensorSource",
    "TransportSessionExporter",
    "TransportSessionRepository",
]
