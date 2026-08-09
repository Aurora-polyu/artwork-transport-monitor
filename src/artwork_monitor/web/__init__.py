"""Optional Flask interface layer; importing the core package never requires Flask."""

from .app import create_app
from .capabilities import (
    CapabilityState,
    ComponentCapability,
    PhysicalValidation,
    RuntimeCapabilities,
)
from .services import WebDependencies, create_demo_dependencies

__all__ = [
    "CapabilityState",
    "ComponentCapability",
    "PhysicalValidation",
    "RuntimeCapabilities",
    "WebDependencies",
    "create_app",
    "create_demo_dependencies",
]
