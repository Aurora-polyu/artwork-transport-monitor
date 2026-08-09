"""Optional Flask interface layer; importing the core package never requires Flask."""

from .app import create_app
from .services import WebDependencies

__all__ = ["WebDependencies", "create_app"]
