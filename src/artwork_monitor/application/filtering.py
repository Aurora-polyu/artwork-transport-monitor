"""Legacy-compatible, stateful filtering with no runtime dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EwmaFilter:
    """An EWMA whose state survives unavailable measurements until reset."""

    alpha: float
    _value: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha <= 1.0:
            raise ValueError("alpha must be greater than 0 and no greater than 1")

    def update(self, value: float | None) -> float | None:
        """Return the filtered observation; ``None`` preserves prior state."""

        if value is None:
            return None
        if self._value is None:
            self._value = value
        else:
            self._value = self.alpha * value + (1.0 - self.alpha) * self._value
        return self._value

    def reset(self) -> None:
        """Forget all previous valid observations."""

        self._value = None


@dataclass(slots=True)
class EnvironmentalFilters:
    """The three owner-characterized environmental EWMA filters."""

    temperature: EwmaFilter = field(default_factory=lambda: EwmaFilter(alpha=0.1))
    humidity: EwmaFilter = field(default_factory=lambda: EwmaFilter(alpha=0.1))
    light: EwmaFilter = field(default_factory=lambda: EwmaFilter(alpha=0.3))

    def reset(self) -> None:
        self.temperature.reset()
        self.humidity.reset()
        self.light.reset()


def clean_gravity_deviation(gravity_deviation_g: float | None) -> float | None:
    """Preserve the legacy cutoff: available values below 0.02 g become zero."""

    if gravity_deviation_g is None:
        return None
    return 0.0 if gravity_deviation_g < 0.02 else gravity_deviation_g
