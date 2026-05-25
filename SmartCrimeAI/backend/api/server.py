"""server.py — FastAPI REST server for Unity frontend consumption."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


# ─────────────────────────────────────────────────────────────────────────────
# Simulation state container (shared between the simulation loop and the API)
# ─────────────────────────────────────────────────────────────────────────────

class SimulationState:
    """Thread-safe container that holds references to every shared object.

    The simulation loop and the API server both access this; mutations are
    protected by ``self.lock``.
    """

    def __init__(self) -> None:
        self.environment: Any = None
        self.civilians: List[Any] = []
        self.criminals: List[Any] = []
        self.police: List[Any] = []
        self.crime_log: Any = None
        self.metric_logger: Any = None
        self.scenario_engine: Any = None
        self.patrol_routes: Dict[str, List[str]] = {}
        self.predictor: Any = None

        self.lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_native(value: Any) -> Any:
    """Convert numpy scalars / arrays to plain Python types for JSON."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _agent_dict(agent: Any, agent_type: str) -> Dict[str, Any]:
    """Serialise an agent to a JSON-safe dictionary."""
    return {
        "id": str(agent.agent_id),
        "type": agent_type,
        "zone": str(agent.zone_id),
        "x": _to_native(getattr(agent, "x", 0.0)),
        "z": _to_native(getattr(agent, "z", 0.0)),
        "state": str(getattr(agent, "state", "idle")),
    }


def _zone_dict(zone: Any) -> Dict[str, Any]:
    """Serialise a zone to a JSON-safe dictionary."""
    return {
        "id": str(zone.zone_id),
        "zone_type": str(getattr(zone, "zone_type", "unknown")),
        "risk_score": _to_native(zone.risk_score),
        "lighting": _to_native(getattr(zone, "lighting", 1.0)),
        "population": _to_native(getattr(zone, "population", 0)),
        "police_count": _to_native(getattr(zone, "police_count", 0)),
        "is_hotspot": bool(getattr(zone, "is_hotspot", False)),
    }


def _crime_event_dict(event: Any) -> Dict[str, Any]:
    """Serialise a crime event to a JSON-safe dictionary."""
    return {
        "id": str(getattr(event, "crime_id", "")),
        "zone": str(getattr(event, "zone_id", "")),
        "time_of_day": _to_native(getattr(event, "time_of_day", 0.0)),
        "type": str(getattr(event, "crime_type", "unknown")),
        "caught": bool(getattr(event, "caught", False)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────────────────────

def create_app(sim_state: SimulationState) -> FastAPI:
    """Build and return a fully-configured FastAPI application."""

    app = FastAPI(
        title="Smart Crime AI — Backend API",
        description="REST endpoints consumed by the Unity frontend.",
        version="1.0.0",
    )

    # --- CORS middleware (allow everything for development) ---------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── GET /state ──────────────────────────────────────────────────────

    @app.get("/state")
    def get_state() -> Dict[str, Any]:
        """Full snapshot of the current simulation state."""
        with sim_state.lock:
            env = sim_state.environment

            # Agents
            agents: List[Dict[str, Any]] = []
            for civ in sim_state.civilians:
                agents.append(_agent_dict(civ, "civilian"))
            for crim in sim_state.criminals:
                agents.append(_agent_dict(crim, "criminal"))
            for pol in sim_state.police:
                agents.append(_agent_dict(pol, "police"))

            # Zones
            zones: List[Dict[str, Any]] = []
            for zid in env.zone_ids:
                zone = env.get_zone(zid)
                zones.append(_zone_dict(zone))

            # Crime events (most recent 10)
            crime_events: List[Dict[str, Any]] = []
            if sim_state.crime_log is not None:
                recent = sim_state.crime_log.get_recent(10)
                for ev in recent:
                    crime_events.append(_crime_event_dict(ev))

            return {
                "tick": _to_native(env.tick),
                "time_of_day": _to_native(env.time_of_day),
                "agents": agents,
                "zones": zones,
                "patrol_routes": {
                    str(k): [str(z) for z in v]
                    for k, v in sim_state.patrol_routes.items()
                },
                "crime_events": crime_events,
            }

    # ── GET /hotspots ───────────────────────────────────────────────────

    @app.get("/hotspots")
    def get_hotspots() -> List[Dict[str, Any]]:
        """Return zones flagged as hotspots."""
        with sim_state.lock:
            env = sim_state.environment
            result: List[Dict[str, Any]] = []
            for zid in env.zone_ids:
                zone = env.get_zone(zid)
                if getattr(zone, "is_hotspot", False):
                    result.append(_zone_dict(zone))
            return result

    # ── GET /patrol-routes ──────────────────────────────────────────────

    @app.get("/patrol-routes")
    def get_patrol_routes() -> Dict[str, List[str]]:
        """Current patrol route assignments."""
        with sim_state.lock:
            return {
                str(k): [str(z) for z in v]
                for k, v in sim_state.patrol_routes.items()
            }

    # ── GET /metrics ────────────────────────────────────────────────────

    @app.get("/metrics")
    def get_metrics() -> Dict[str, Any]:
        """Combined simulation + ML metrics."""
        with sim_state.lock:
            metrics: Dict[str, Any] = {}
            if sim_state.metric_logger is not None:
                base = sim_state.metric_logger.get_metrics()
                metrics.update(
                    {str(k): _to_native(v) for k, v in base.items()}
                )
            # Merge ML metrics if available
            ml_metrics = getattr(sim_state.metric_logger, "ml_metrics", None)
            if ml_metrics:
                metrics["ml_metrics"] = {
                    str(k): _to_native(v) for k, v in ml_metrics.items()
                }
            return metrics

    # ── GET /crime-events ───────────────────────────────────────────────

    @app.get("/crime-events")
    def get_crime_events(
        limit: int = Query(default=20, ge=1, le=500),
    ) -> List[Dict[str, Any]]:
        """Return the *limit* most recent crime events."""
        with sim_state.lock:
            if sim_state.crime_log is None:
                return []
            recent = sim_state.crime_log.get_recent(limit)
            return [_crime_event_dict(ev) for ev in recent]

    # ── POST /scenario ──────────────────────────────────────────────────

    @app.post("/scenario")
    def apply_scenario(body: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a scenario change (e.g. toggle patrol mode, inject event)."""
        with sim_state.lock:
            if sim_state.scenario_engine is None:
                return {"status": "error", "detail": "scenario engine not initialised"}
            try:
                result = sim_state.scenario_engine.apply(body)
                return {"status": "ok", "result": result}
            except Exception as exc:  # noqa: BLE001
                return {"status": "error", "detail": str(exc)}

    return app
