"""Safe command-line entry point for inspecting configuration."""

from __future__ import annotations

import argparse
import os

from .adapters.simulated import run_simulated_session
from .adapters.simulated.scenarios import normal_transport
from .config import Settings


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

    print("simulated normal transport session")
    for result in run_simulated_session(normal_transport(), (0.0, 2.0)):
        reading = result.reading
        print(
            f"step={result.monotonic_seconds:.1f} "
            f"temperature={reading.temperature_c:.2f}C "
            f"humidity={reading.humidity_percent_rh:.2f}%RH "
            f"light={reading.light_lux:.2f}lux "
            f"immediate={len(result.immediate_violations)} "
            f"prolonged={len(result.prolonged_violations)}"
        )


if __name__ == "__main__":
    main()
