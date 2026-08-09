"""Typed, side-effect-free runtime configuration for the reconstruction."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


class RuntimeProfile(str, Enum):
    """Supported runtime profiles; functionality is added in later milestones."""

    TEST = "test"
    DEMO = "demo"
    HARDWARE = "hardware"
    FULL_TEAM = "full-team"

    @classmethod
    def parse(cls, value: str) -> "RuntimeProfile":
        normalized = value.strip().lower().replace("_", "-")
        try:
            return cls(normalized)
        except ValueError as error:
            choices = ", ".join(profile.value for profile in cls)
            raise ValueError(
                f"Unknown runtime profile {value!r}; choose one of: {choices}"
            ) from error


def _source_project_root() -> Path:
    """Find the repository root from this installed source layout, never CWD."""

    return Path(__file__).resolve().parents[2]


def _path_from_env(value: str | None, *, base: Path, default: Path) -> Path:
    candidate = Path(value).expanduser() if value else default
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def _optional_port(value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError("ARTWORK_MONITOR_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("ARTWORK_MONITOR_PORT must be between 1 and 65535")
    return port


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration only; constructing it performs no I/O or service startup."""

    profile: RuntimeProfile
    project_root: Path
    runtime_dir: Path
    database_path: Path
    log_dir: Path
    flask_secret_key: str | None
    host: str
    port: int
    email_host: str | None
    email_port: int | None
    email_sender: str | None
    email_recipient: str | None
    email_password: str | None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        project_root = _path_from_env(
            env.get("ARTWORK_MONITOR_PROJECT_ROOT"),
            base=_source_project_root(),
            default=_source_project_root(),
        )
        runtime_dir = _path_from_env(
            env.get("ARTWORK_MONITOR_RUNTIME_DIR"),
            base=project_root,
            default=project_root / "instance",
        )
        database_path = _path_from_env(
            env.get("ARTWORK_MONITOR_DATABASE_PATH"),
            base=runtime_dir,
            default=runtime_dir / "artwork_monitor.sqlite3",
        )
        log_dir = _path_from_env(
            env.get("ARTWORK_MONITOR_LOG_DIR"),
            base=runtime_dir,
            default=runtime_dir / "transport_logs",
        )
        email_port_value = env.get("ARTWORK_MONITOR_EMAIL_PORT")
        return cls(
            profile=RuntimeProfile.parse(env.get("ARTWORK_MONITOR_PROFILE", "demo")),
            project_root=project_root,
            runtime_dir=runtime_dir,
            database_path=database_path,
            log_dir=log_dir,
            flask_secret_key=env.get("ARTWORK_MONITOR_FLASK_SECRET") or None,
            host=env.get("ARTWORK_MONITOR_HOST", "127.0.0.1"),
            port=_optional_port(env.get("ARTWORK_MONITOR_PORT"), default=8000),
            email_host=env.get("ARTWORK_MONITOR_EMAIL_HOST") or None,
            email_port=int(email_port_value) if email_port_value else None,
            email_sender=env.get("ARTWORK_MONITOR_EMAIL_SENDER") or None,
            email_recipient=env.get("ARTWORK_MONITOR_EMAIL_RECIPIENT") or None,
            email_password=env.get("ARTWORK_MONITOR_EMAIL_PASSWORD") or None,
        )
