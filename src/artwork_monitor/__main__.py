"""Safe command-line entry point for inspecting configuration."""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import timedelta
from pathlib import Path

from .adapters.notifications import InMemoryNotificationDispatcher
from .adapters.persistence import CsvTransportSessionExporter, SQLiteTransportSessionRepository
from .adapters.simulated import SequenceSensorSource
from .adapters.simulated.scenarios import normal_transport
from .application import MonitoringService, TransportSessionWorkflow, render_markdown
from .config import Settings
from .domain import TransportSession


def main() -> None:
    parser = argparse.ArgumentParser(description="Artwork transportation monitoring")
    parser.add_argument("--profile", choices=("test", "demo", "hardware", "full-team"))
    arguments = parser.parse_args()
    environment = dict(os.environ)
    if arguments.profile:
        environment["ARTWORK_MONITOR_PROFILE"] = arguments.profile
    settings = Settings.from_env(environment)
    print(f"artwork-monitor profile: {settings.profile.value}")
    if settings.profile.value != "demo":
        print(f"runtime directory: {settings.runtime_dir}")
        return

    _run_demo(settings)


def _run_demo(settings: Settings) -> None:
    scenario = normal_transport()
    assert scenario.readings
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    artifact_directory = Path(tempfile.mkdtemp(prefix="artwork-monitor-demo-", dir=settings.runtime_dir))
    repository = SQLiteTransportSessionRepository(artifact_directory / "transport.sqlite3")
    dispatcher = InMemoryNotificationDispatcher()
    service = MonitoringService(
        SequenceSensorSource(scenario.readings),
        session_repository=repository,
        notification_dispatcher=dispatcher,
    )
    workflow = TransportSessionWorkflow(
        service,
        repository,
        csv_exporter=CsvTransportSessionExporter(artifact_directory),
    )
    started_at = scenario.readings[0].timestamp
    workflow.start(TransportSession("demo-normal", started_at))
    workflow.run((0.0, 2.0))
    outcome = workflow.complete(started_at + timedelta(seconds=4))

    print("simulated end-to-end normal transport session")
    print(f"artifacts: {artifact_directory}")
    print(f"sqlite: {artifact_directory / 'transport.sqlite3'}")
    print(f"csv: {outcome.csv_path}")
    print(f"notifications: {len(dispatcher.messages)}")
    print(render_markdown(outcome.report), end="")


if __name__ == "__main__":
    main()
