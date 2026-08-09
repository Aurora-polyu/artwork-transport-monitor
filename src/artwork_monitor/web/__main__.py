"""Run the optional, software-only Flask interface without hardware services."""

from __future__ import annotations

import argparse

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Software-only artwork monitoring web demo"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    app = create_app()
    app.extensions["socketio"].run(
        app,
        host=arguments.host,
        port=arguments.port,
        debug=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
