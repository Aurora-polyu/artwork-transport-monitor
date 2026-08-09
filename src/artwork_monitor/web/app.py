"""Safe Flask factory for the clean, synchronous application services."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from artwork_monitor.application import TransportSessionState
from artwork_monitor.domain import HONG_KONG, TransportSession

from .services import WebDependencies, create_demo_dependencies
from .realtime import RealtimeEventAdapter
from .serialization import dashboard_session, timestamp, violation


def create_app(*, dependencies: WebDependencies | None = None, database_path: Path | None = None):
    """Create routes only; never start hardware, threads, loops, or notifications."""

    try:
        from flask import Flask, abort, jsonify, render_template, request
        from flask_socketio import SocketIO, emit
    except ModuleNotFoundError as error:
        if error.name == "flask":
            raise RuntimeError("Flask is optional; install artwork-transportation-monitor[web]") from error
        raise

    if dependencies is None:
        path = database_path or Path(mkdtemp(prefix="artwork-monitor-web-")) / "web.sqlite3"
        dependencies = create_demo_dependencies(path)

    app = Flask(__name__)
    app.extensions["artwork_monitor_dependencies"] = dependencies
    socketio = SocketIO(app, async_mode="threading")
    app.extensions["socketio"] = socketio
    realtime = RealtimeEventAdapter(socketio)

    @socketio.on("connect")
    def socket_connect():
        emit("state_snapshot", _snapshot(dependencies))

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/transport")
    def transport_page():
        return render_template("transport.html", state=dependencies.transport_workflow.state.value)

    @app.get("/transport/status")
    def transport_status():
        return jsonify({"state": dependencies.transport_workflow.state.value})

    @app.get("/api/dashboard/capabilities")
    def dashboard_capabilities():
        return jsonify({"components": dependencies.runtime_capabilities.as_dict()})

    @app.post("/transport/start")
    def transport_start():
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            return jsonify({"error": "session_id is required"}), 400
        try:
            started_at = _parse_timestamp(data.get("started_at"))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        try:
            dependencies.transport_workflow.start(TransportSession(session_id.strip(), started_at))
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 409
        payload = {"state": dependencies.transport_workflow.state.value, "session_id": session_id.strip()}
        realtime.publish("transport_started", payload)
        return jsonify(payload), 201

    @app.post("/transport/step")
    def transport_step():
        data = request.get_json(silent=True) or {}
        try:
            monotonic_seconds = float(data["monotonic_seconds"])
            cycle = dependencies.transport_workflow.step(monotonic_seconds)
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "monotonic_seconds must be numeric"}), 400
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 409
        payload = {"processed": cycle is not None}
        if cycle is not None:
            session_id = dependencies.transport_workflow.session_id
            assert session_id is not None
            realtime.publish("transport_cycle", _cycle_payload(session_id, cycle))
            if cycle.gps_fix is not None and cycle.gps_fix.is_available:
                realtime.publish("gps_update", {"session_id": session_id, "timestamp": timestamp(cycle.gps_fix.timestamp), "latitude": cycle.gps_fix.latitude, "longitude": cycle.gps_fix.longitude})
            for kind, violations in (("immediate", cycle.immediate_violations), ("prolonged", cycle.prolonged_violations)):
                for violation in violations:
                    realtime.publish("violation", {"session_id": session_id, "kind": kind, **_violation_payload(violation)})
        return jsonify(payload)

    @app.post("/transport/stop")
    def transport_stop():
        data = request.get_json(silent=True) or {}
        try:
            completed = dependencies.transport_workflow.complete(_parse_timestamp(data.get("ended_at")))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 409
        payload = {"state": TransportSessionState.COMPLETED.value, "session_id": completed.stored_session.session.session_id}
        realtime.publish("transport_completed", payload)
        realtime.publish("report_ready", {"session_id": completed.stored_session.session.session_id, "report_url": f"/report?session_id={completed.stored_session.session.session_id}"})
        return jsonify(payload)

    @app.get("/check")
    def check_page():
        return render_template("check.html", checking=dependencies.artwork_workflow.checking, artworks=_artworks(dependencies))

    @app.get("/check/status")
    def check_status():
        return jsonify({"checking": dependencies.artwork_workflow.checking, "artworks": _artworks(dependencies)})

    @app.post("/check/start")
    def check_start():
        dependencies.artwork_workflow.start()
        realtime.publish("artwork_check_started", {"checking": True, "artworks": _artworks(dependencies)})
        return jsonify({"checking": True})

    @app.post("/check/step")
    def check_step():
        step = dependencies.artwork_workflow.process_next_frame()
        transition = _transition(step.transition) if step else None
        if transition is not None:
            realtime.publish("artwork_status_changed", {"transition": transition, "artworks": _artworks(dependencies)})
        return jsonify({"processed": step is not None, "transition": transition})

    @app.post("/check/stop")
    def check_stop():
        dependencies.artwork_workflow.stop()
        realtime.publish("artwork_check_stopped", {"checking": False, "artworks": _artworks(dependencies)})
        return jsonify({"checking": False})

    @app.get("/report")
    def report_page():
        session_id = request.args.get("session_id")
        report = _report_or_none(dependencies, session_id, abort)
        return render_template("report.html", session_ids=dependencies.session_repository.list_session_ids(), report=report)

    @app.get("/history")
    def history_page():
        return render_template("report.html", session_ids=dependencies.session_repository.list_session_ids(), report=None)

    @app.get("/api/report/data")
    def report_data():
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"error": "session_id is required"}), 400
        report = _report_or_none(dependencies, session_id, abort)
        assert report is not None
        return jsonify(_report_json(report))

    @app.get("/gps")
    def gps_page():
        return render_template("gps.html", session_ids=dependencies.session_repository.list_session_ids())

    @app.get("/api/gps/history")
    def gps_history():
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"error": "session_id is required"}), 400
        try:
            stored = dependencies.session_repository.load_session(session_id)
        except KeyError:
            abort(404)
        points = [
            {"timestamp": timestamp(record.gps_fix.timestamp), "latitude": record.gps_fix.latitude, "longitude": record.gps_fix.longitude}
            for record in stored.records
            if record.gps_fix is not None and record.gps_fix.is_available
        ]
        return jsonify({"session_id": session_id, "points": points})

    @app.get("/api/sessions/<session_id>/dashboard-data")
    def dashboard_session_data(session_id: str):
        try:
            stored = dependencies.session_repository.load_session(session_id)
        except KeyError:
            abort(404)
        return jsonify(dashboard_session(stored))

    return app


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is required as ISO-8601 text")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("timestamp must be ISO-8601 text") from error
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=HONG_KONG)


def _artworks(dependencies: WebDependencies) -> list[dict[str, str | int | None]]:
    return [
        {"label_index": label, "name": state.identity.name, "lot": state.identity.lot, "status": state.status.value,
         "time_in": timestamp(state.time_in) if state.time_in else None, "time_out": timestamp(state.time_out) if state.time_out else None}
        for label, state in dependencies.artwork_workflow.states().items()
    ]


def _transition(transition):
    if transition is None:
        return None
    return {"label_index": transition.label_index, "status": transition.status.value, "occurred_at": timestamp(transition.occurred_at)}


def _report_or_none(dependencies: WebDependencies, session_id: str | None, abort):
    if session_id is None:
        return None
    try:
        return dependencies.report_generator.generate_from_repository(dependencies.session_repository, session_id)
    except KeyError:
        abort(404)


def _report_json(report) -> dict[str, Any]:
    return {
        "session_id": report.session_id,
        "started_at": report.started_at,
        "ended_at": report.ended_at,
        "monitoring_cycle_count": report.monitoring_cycle_count,
        "temperature": {"minimum": report.temperature.minimum, "maximum": report.temperature.maximum, "mean": report.temperature.mean},
        "humidity": {"minimum": report.humidity.minimum, "maximum": report.humidity.maximum, "mean": report.humidity.mean},
        "light": {"minimum": report.light.minimum, "maximum": report.light.maximum, "mean": report.light.mean},
        "gps": {"available_fix_count": report.gps.available_fix_count},
    }


def _snapshot(dependencies: WebDependencies) -> dict[str, Any]:
    return {
        "transport": {"state": dependencies.transport_workflow.state.value, "session_id": dependencies.transport_workflow.session_id},
        "artwork": {"checking": dependencies.artwork_workflow.checking, "artworks": _artworks(dependencies)},
        "session_ids": list(dependencies.session_repository.list_session_ids()),
        "capabilities": {"components": dependencies.runtime_capabilities.as_dict()},
    }


def _cycle_payload(session_id: str, cycle) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "monotonic_seconds": cycle.monotonic_seconds,
        "reading": {"timestamp": timestamp(cycle.reading.timestamp), "temperature_c": cycle.reading.temperature_c, "humidity_percent_rh": cycle.reading.humidity_percent_rh, "light_lux": cycle.reading.light_lux, "gravity_deviation_g": cycle.reading.gravity_deviation_g},
        "immediate_conditions": [violation.condition.value for violation in cycle.immediate_violations],
        "prolonged_conditions": [violation.condition.value for violation in cycle.prolonged_violations],
    }


def _violation_payload(item) -> dict[str, Any]:
    return violation(item)
