"""Explicit software-only dependency wiring for the Flask interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from artwork_monitor.adapters.persistence import SQLiteTransportSessionRepository
from artwork_monitor.adapters.simulated import (
    PassthroughImagePreprocessor,
    SequenceCameraSource,
    SequenceDetector,
    SequenceGPSFixSource,
    SequenceSensorSource,
)
from artwork_monitor.adapters.simulated.scenarios import gps_route, normal_transport
from artwork_monitor.application import ArtworkWorkflow, MonitoringService, SessionReportGenerator, TransportSessionWorkflow
from artwork_monitor.domain import InferenceResult
from artwork_monitor.ports import CameraFrame, TransportSessionRepository

from .capabilities import RuntimeCapabilities


@dataclass(frozen=True, slots=True)
class WebDependencies:
    """All services used by one Flask application instance."""

    session_repository: TransportSessionRepository
    report_generator: SessionReportGenerator
    artwork_workflow: ArtworkWorkflow
    transport_workflow: TransportSessionWorkflow
    runtime_capabilities: RuntimeCapabilities


def create_demo_dependencies(database_path: Path) -> WebDependencies:
    """Construct finite, inactive software-only services without running them."""

    repository = SQLiteTransportSessionRepository(database_path)
    scenario = normal_transport()
    route = gps_route()
    monitoring = MonitoringService(
        SequenceSensorSource(scenario.readings),
        gps_source=SequenceGPSFixSource(route.fixes),
        session_repository=repository,
    )
    return WebDependencies(
        session_repository=repository,
        report_generator=SessionReportGenerator(),
        artwork_workflow=ArtworkWorkflow(
            camera_source=SequenceCameraSource(CameraFrame(f"web-demo-{index}") for index in range(1, 11)),
            preprocessor=PassthroughImagePreprocessor(),
            detector=SequenceDetector((InferenceResult(0, 0.99), InferenceResult(1, 0.99))),
        ),
        transport_workflow=TransportSessionWorkflow(monitoring, repository),
        runtime_capabilities=RuntimeCapabilities.simulation(),
    )
