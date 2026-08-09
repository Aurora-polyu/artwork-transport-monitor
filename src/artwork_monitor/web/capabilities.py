"""Explicit, truthful runtime capability metadata for web clients."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CapabilityState(str, Enum):
    """What the application has made available to the web interface."""

    SIMULATED = "simulated"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class PhysicalValidation(str, Enum):
    """Whether a component's physical behaviour has been validated."""

    NOT_VALIDATED = "not_validated"
    VALIDATED = "validated"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ComponentCapability:
    """One declared capability without inferring operational health."""

    state: CapabilityState
    physical_validation: PhysicalValidation

    def as_dict(self) -> dict[str, str]:
        return {
            "state": self.state.value,
            "physical_validation": self.physical_validation.value,
        }


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    """Application-configured capability metadata for the dashboard."""

    sensors: ComponentCapability
    gps: ComponentCapability
    artwork: ComponentCapability
    storage: ComponentCapability
    realtime: ComponentCapability

    @classmethod
    def simulation(cls) -> "RuntimeCapabilities":
        """Describe the supplied software-only demonstration dependencies."""

        simulated = ComponentCapability(
            CapabilityState.SIMULATED, PhysicalValidation.NOT_VALIDATED
        )
        available = ComponentCapability(
            CapabilityState.AVAILABLE, PhysicalValidation.NOT_APPLICABLE
        )
        return cls(
            sensors=simulated,
            gps=simulated,
            artwork=simulated,
            storage=available,
            realtime=available,
        )

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {
            "sensors": self.sensors.as_dict(),
            "gps": self.gps.as_dict(),
            "artwork": self.artwork.as_dict(),
            "storage": self.storage.as_dict(),
            "realtime": self.realtime.as_dict(),
        }
