"""server.py — FastAPI REST server for Unity frontend consumption."""

from __future__ import annotations

import threading
import asyncio
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


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
        self.gnn_trainer: Any = None
        self.marl_coordinator: Any = None

        self.lock = threading.Lock()
        self.ws_clients: List[WebSocket] = []
        self.loop = None

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Serializes current environment and agents safely to a dictionary."""
        env = self.environment
        if env is None:
            return {}

        # Agents
        agents: List[Dict[str, Any]] = []
        for civ in self.civilians:
            agents.append(_agent_dict(civ, "civilian"))
        for crim in self.criminals:
            agents.append(_agent_dict(crim, "criminal"))
        for pol in self.police:
            agents.append(_agent_dict(pol, "police"))

        # Zones
        zones: List[Dict[str, Any]] = []
        for zid in env.zone_ids:
            zone = env.get_zone(zid)
            zones.append(_zone_dict(zone))

        # Crime events (most recent 10)
        crime_events: List[Dict[str, Any]] = []
        if self.crime_log is not None:
            recent = self.crime_log.get_recent(10)
            for ev in recent:
                crime_events.append(_crime_event_dict(ev))

        return {
            "tick": _to_native(env.tick),
            "time_of_day": _to_native(env.time_of_day),
            "agents": agents,
            "zones": zones,
            "patrol_routes": {
                str(k): [str(z) for z in v]
                for k, v in self.patrol_routes.items()
            },
            "crime_events": crime_events,
        }

    def broadcast_state(self) -> None:
        """Broadcasts simulation snapshot to all connected WebSocket clients thread-safely."""
        if not self.ws_clients:
            return

        state_data = self.get_state_snapshot()
        if not state_data:
            return

        async def _broadcast():
            disconnected = []
            for ws in list(self.ws_clients):
                try:
                    await ws.send_json(state_data)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                if ws in self.ws_clients:
                    self.ws_clients.remove(ws)

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(), self.loop)
        else:
            try:
                asyncio.run(_broadcast())
            except Exception:
                pass


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
    if isinstance(event, dict):
        return {
            "id": str(event.get("crime_id", "")),
            "zone": str(event.get("zone_id", "")),
            "time_of_day": _to_native(event.get("time_of_day", 0.0)),
            "type": str(event.get("crime_type", "unknown")),
            "caught": bool(event.get("caught", False)),
        }
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
    
    # Store reference to the FastAPI event loop for background thread broadcasting
    import asyncio
    sim_state.loop = asyncio.get_event_loop()

    app = FastAPI(
        title="Smart Crime AI — Backend API",
        description="REST endpoints consumed by the Unity frontend.",
        version="1.0.0",
    )

    # --- Mount Static Reports Directory -----------------------------------
    import os
    os.makedirs("output/reports", exist_ok=True)
    app.mount("/reports", StaticFiles(directory="output/reports"), name="reports")

    # --- CORS middleware (allow everything for development) ---------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── WebSocket /ws/state ──────────────────────────────────────────────

    @app.websocket("/ws/state")
    async def websocket_state(websocket: WebSocket):
        """Websocket endpoint streaming state live every simulation tick."""
        await websocket.accept()
        sim_state.ws_clients.append(websocket)
        try:
            # Send initial state snapshot immediately
            await websocket.send_json(sim_state.get_state_snapshot())
            while True:
                # Keep connection alive by waiting for client messages or disconnects
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in sim_state.ws_clients:
                sim_state.ws_clients.remove(websocket)

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

    # ── GET /reports ────────────────────────────────────────────────────

    @app.get("/reports")
    def get_reports() -> Dict[str, Any]:
        """Return the latest generated training report snapshot."""
        import json
        import os
        latest_path = "output/latest_report.json"
        if os.path.isfile(latest_path):
            try:
                with open(latest_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"error": "No reports generated yet. Run some simulation ticks to trigger retrains."}

    # ── GET /training-history ───────────────────────────────────────────

    @app.get("/training-history")
    def get_training_history() -> List[Dict[str, Any]]:
        """Return the entire historical record of model retrain cycles."""
        import json
        import os
        history_path = "output/training_history.json"
        if os.path.isfile(history_path):
            try:
                with open(history_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return []

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

    # ── GET / (HTML Dashboard) ──────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    def serve_dashboard() -> str:
        """Serve a gorgeous dark-mode web control center to visualize the simulation."""
        return DASHBOARD_HTML

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Built-in High-Fidelity Web Dashboard (HTML / CSS / JS)
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart Crime Prediction & Patrol Optimizer — Control Room</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #070b13;
      --card-bg: rgba(17, 24, 39, 0.7);
      --border: rgba(255, 255, 255, 0.08);
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --accent-blue: #3b82f6;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-orange: #f59e0b;
      --accent-purple: #8b5cf6;
      
      --zone-res: #1e293b;
      --zone-com: #2e1065;
      --zone-park: #064e3b;
      --zone-int: #0f172a;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Outfit', sans-serif;
    }

    body {
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.08) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.08) 0px, transparent 50%);
      color: var(--text-primary);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }

    /* Header styling */
    header {
      backdrop-filter: blur(12px);
      background: rgba(15, 23, 42, 0.6);
      border-bottom: 1px solid var(--border);
      padding: 1.25rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .brand-logo {
      width: 2.25rem;
      height: 2.25rem;
      border-radius: 0.5rem;
      background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.25rem;
      box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
    }

    .brand-text h1 {
      font-size: 1.25rem;
      font-weight: 600;
      letter-spacing: -0.025em;
    }

    .brand-text p {
      font-size: 0.75rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .header-telemetry {
      display: flex;
      gap: 1.5rem;
      align-items: center;
    }

    .tel-item {
      text-align: right;
    }

    .tel-lbl {
      font-size: 0.7rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .tel-val {
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--text-primary);
    }

    .tel-val.mono {
      font-family: 'JetBrains Mono', monospace;
    }

    /* Main Container */
    .dashboard-container {
      flex: 1;
      padding: 2rem;
      max-width: 1400px;
      margin: 0 auto;
      width: 100%;
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 2rem;
    }

    @media (max-width: 1024px) {
      .dashboard-container {
        grid-template-columns: 1fr;
      }
    }

    /* Card Styling */
    .glass-card {
      backdrop-filter: blur(12px);
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: 1.5rem;
      box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
    }

    .card-title {
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.75rem;
    }

    /* Map Layout */
    .map-container {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .grid-board {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      grid-template-rows: repeat(6, 1fr);
      gap: 0.75rem;
      aspect-ratio: 1;
      width: 100%;
    }

    .zone-cell {
      border-radius: 0.75rem;
      border: 1px solid rgba(255, 255, 255, 0.05);
      padding: 0.75rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      overflow: hidden;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
    }

    .zone-cell:hover {
      transform: translateY(-2px);
      border-color: rgba(255, 255, 255, 0.2);
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }

    .zone-cell.residential { background-color: var(--zone-res); }
    .zone-cell.commercial { background-color: var(--zone-com); }
    .zone-cell.park { background-color: var(--zone-park); }
    .zone-cell.intersection { background-color: var(--zone-int); }

    .zone-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      z-index: 2;
    }

    .zone-id {
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      font-size: 0.9rem;
    }

    .zone-type-badge {
      font-size: 0.6rem;
      text-transform: uppercase;
      padding: 0.15rem 0.35rem;
      border-radius: 0.25rem;
      background: rgba(255, 255, 255, 0.1);
      color: var(--text-secondary);
    }

    .zone-risk {
      font-size: 0.75rem;
      font-weight: 500;
      z-index: 2;
      display: flex;
      align-items: center;
      gap: 0.25rem;
    }

    .zone-agents {
      display: flex;
      flex-wrap: wrap;
      gap: 0.25rem;
      margin-top: 0.5rem;
      z-index: 2;
      min-height: 1.5rem;
      align-items: flex-end;
    }

    /* Hotspot glow pulse */
    @keyframes hotspot-pulse {
      0% { box-shadow: inset 0 0 10px rgba(239, 68, 68, 0.4), 0 0 5px rgba(239, 68, 68, 0.2); }
      50% { box-shadow: inset 0 0 20px rgba(239, 68, 68, 0.8), 0 0 15px rgba(239, 68, 68, 0.5); }
      100% { box-shadow: inset 0 0 10px rgba(239, 68, 68, 0.4), 0 0 5px rgba(239, 68, 68, 0.2); }
    }

    .zone-cell.hotspot {
      animation: hotspot-pulse 2s infinite;
      border: 1.5px solid var(--accent-red) !important;
    }

    /* Agent Badges */
    .agent-dot {
      width: 1.1rem;
      height: 1.1rem;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.65rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      cursor: help;
      transition: all 0.2s;
    }

    .agent-dot:hover {
      transform: scale(1.3);
      z-index: 10;
    }

    .agent-dot.civilian { background-color: var(--accent-green); color: white; }
    .agent-dot.police { background-color: var(--accent-blue); color: white; }
    .agent-dot.criminal { background-color: var(--accent-orange); color: white; }

    /* Side Panel Widgets */
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 1rem;
    }

    .metric-card {
      background: rgba(255,255,255, 0.02);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1rem;
      text-align: center;
    }

    .metric-lbl {
      font-size: 0.75rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }

    .metric-val {
      font-size: 1.5rem;
      font-weight: 700;
    }

    .metric-val.blue { color: var(--accent-blue); }
    .metric-val.green { color: var(--accent-green); }
    .metric-val.red { color: var(--accent-red); }
    .metric-val.purple { color: var(--accent-purple); }

    /* Controls Panel */
    .controls-panel {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }

    .btn-group {
      display: flex;
      gap: 0.5rem;
    }

    button {
      flex: 1;
      padding: 0.75rem 1rem;
      border-radius: 0.5rem;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-primary);
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
    }

    button:hover {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.3);
      transform: translateY(-1px);
    }

    button:active {
      transform: translateY(1px);
    }

    button.primary {
      background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
      border: none;
      box-shadow: 0 4px 10px rgba(59, 130, 246, 0.2);
    }

    button.primary:hover {
      box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
      filter: brightness(1.1);
    }

    button.danger {
      background: rgba(239, 68, 68, 0.2);
      border-color: rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }

    button.danger:hover {
      background: rgba(239, 68, 68, 0.4);
      border-color: var(--accent-red);
    }

    /* Live Feed logs */
    .log-feed {
      height: 180px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      padding-right: 0.5rem;
    }

    .log-item {
      display: flex;
      justify-content: space-between;
      padding: 0.5rem;
      border-radius: 0.35rem;
      background: rgba(255, 255, 255, 0.02);
      border-left: 3px solid #94a3b8;
    }

    .log-item.caught {
      border-left-color: var(--accent-green);
      background: rgba(16, 185, 129, 0.05);
    }

    .log-item.crime {
      border-left-color: var(--accent-red);
      background: rgba(239, 68, 68, 0.05);
    }

    /* Scrollbars */
    ::-webkit-scrollbar {
      width: 6px;
    }
    ::-webkit-scrollbar-track {
      background: rgba(0,0,0,0.1);
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.15);
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(255,255,255,0.3);
    }

    /* Tooltip card on cell hover */
    .tooltip-card {
      position: absolute;
      bottom: 105%;
      left: 50%;
      transform: translateX(-50%) scale(0.95);
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      padding: 0.75rem;
      width: 180px;
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      font-size: 0.75rem;
      color: var(--text-secondary);
    }

    .zone-cell:hover .tooltip-card {
      opacity: 1;
      transform: translateX(-50%) scale(1);
    }

    .tt-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.25rem;
    }

    .tt-val {
      font-weight: 600;
      color: var(--text-primary);
    }
  </style>
</head>
<body>

  <!-- Top bar navigation -->
  <header>
    <div class="brand">
      <div class="brand-logo">🕵️‍♂️</div>
      <div class="brand-text">
        <h1>Smart Crime Prediction</h1>
        <p>Simulation Control & Telemetry Room</p>
      </div>
    </div>
    <div class="header-telemetry">
      <div class="tel-item">
        <div class="tel-lbl">Simulation Time</div>
        <div id="sim-time" class="tel-val mono">--:--</div>
      </div>
      <div class="tel-item">
        <div class="tel-lbl">Grid Tick</div>
        <div id="sim-tick" class="tel-val mono">0</div>
      </div>
      <div class="tel-item">
        <div class="tel-lbl">Patrol Mode</div>
        <div id="patrol-mode-badge" class="tel-val" style="color:var(--accent-purple)">Greedy</div>
      </div>
    </div>
  </header>

  <!-- Dashboard Grid -->
  <div class="dashboard-container">
    
    <!-- Left panel: Map Visualizer -->
    <div class="glass-card map-container">
      <div class="card-title">
        <span>6×6 Virtual City Grid</span>
        <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-secondary);">
          🟢 Civilian | 🔵 Police | 🟡 Criminal
        </span>
      </div>
      <div id="board" class="grid-board">
        <!-- Cells generated by JS -->
      </div>
    </div>

    <!-- Right panel: Telemetry stats & Logs -->
    <div class="sidebar">
      
      <!-- Metrics Card -->
      <div class="glass-card">
        <div class="card-title">Performance Metrics</div>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-lbl">Total Crimes</div>
            <div id="m-total-crimes" class="metric-val red">0</div>
          </div>
          <div class="metric-card">
            <div class="metric-lbl">Arrests / Intercepts</div>
            <div id="m-caught-crimes" class="metric-val green">0</div>
          </div>
          <div class="metric-card">
            <div class="metric-lbl">Intercept Rate</div>
            <div id="m-catch-rate" class="metric-val purple">0.0%</div>
          </div>
          <div class="metric-card">
            <div class="metric-lbl">Avg Response Time</div>
            <div id="m-resp-time" class="metric-val blue">-- ticks</div>
          </div>
          <div class="metric-card" style="grid-column: span 2">
            <div class="metric-lbl">Patrol Coverage Efficiency</div>
            <div id="m-patrol-eff" class="metric-val" style="color: var(--accent-orange)">0.0%</div>
          </div>
        </div>
      </div>

      <!-- Controls Card -->
      <div class="glass-card">
        <div class="card-title">Scenario Interventions</div>
        <div class="controls-panel">
          <div class="btn-group" style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <button onclick="setPatrolMode('greedy')" id="btn-mode-greedy" class="primary" style="flex:1;">Greedy</button>
            <button onclick="setPatrolMode('ai')" id="btn-mode-ai" style="flex:1;">Centralized RL</button>
            <button onclick="setPatrolMode('marl')" id="btn-mode-marl" style="flex:1.2;">MARL Co-op</button>
          </div>
          <div class="btn-group">
            <button onclick="spawnPolice(1)">➕ Dispatch Officer</button>
            <button onclick="spawnPolice(-1)" class="danger">➖ Recall Officer</button>
          </div>
          <div class="btn-group">
            <button onclick="spawnCivilians(5)">🚶 Spawn Civilians (+5)</button>
          </div>
          <button onclick="resetMetrics()" class="danger" style="margin-top:0.5rem">🔄 Reset Statistics</button>
        </div>
      </div>

      <!-- ML Reports & Confidence Curves -->
      <div class="glass-card" id="ml-reports-card" style="display:none;">
        <div class="card-title">ML Retrain Report & Curves</div>
        <div style="display:flex; flex-direction:column; gap:0.75rem;">
          <div style="font-size:0.8rem; color:var(--text-secondary);">
            Dataset Size: <span id="rep-dataset-size" style="font-weight:bold; color:var(--text-primary);">0</span> rows
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem;">
            <img id="chart-comparison" style="width:100%; border-radius:0.5rem; border:1px solid var(--border); cursor:pointer;" onclick="window.open(this.src)" title="Click to enlarge Comparison" />
            <img id="chart-importance" style="width:100%; border-radius:0.5rem; border:1px solid var(--border); cursor:pointer;" onclick="window.open(this.src)" title="Click to enlarge Feature Importance" />
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem;">
            <img id="chart-confusion" style="width:100%; border-radius:0.5rem; border:1px solid var(--border); cursor:pointer;" onclick="window.open(this.src)" title="Click to enlarge Confusion Matrix" />
            <img id="chart-roc" style="width:100%; border-radius:0.5rem; border:1px solid var(--border); cursor:pointer;" onclick="window.open(this.src)" title="Click to enlarge ROC Curve" />
          </div>
        </div>
      </div>

      <!-- Crime Events Live Feed -->
      <div class="glass-card">
        <div class="card-title">Live Dispatch Feed</div>
        <div id="log-feed" class="log-feed">
          <!-- Populated by JS -->
          <div style="color:var(--text-secondary); text-align:center; padding-top:2rem;">Waiting for logs...</div>
        </div>
      </div>

    </div>

  </div>

  <script>
    // Initialize board cell placeholders
    const board = document.getElementById('board');
    const rows = ['A', 'B', 'C', 'D', 'E', 'F'];
    
    // Create 36 cells once, then update dynamic values
    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 6; c++) {
        const id = `${rows[r]}${c}`;
        const cell = document.createElement('div');
        cell.id = `cell-${id}`;
        cell.className = 'zone-cell';
        cell.innerHTML = `
          <div class="zone-header">
            <span class="zone-id">${id}</span>
            <span id="badge-${id}" class="zone-type-badge">-</span>
          </div>
          <div id="risk-${id}" class="zone-risk"></div>
          <div id="agents-${id}" class="zone-agents"></div>
          
          <div class="tooltip-card">
            <div class="tt-row">Type: <span id="tt-type-${id}" class="tt-val">-</span></div>
            <div class="tt-row">Lighting: <span id="tt-light-${id}" class="tt-val">1.0</span></div>
            <div class="tt-row">Population: <span id="tt-pop-${id}" class="tt-val">0</span></div>
            <div class="tt-row">Police Count: <span id="tt-pol-${id}" class="tt-val">0</span></div>
            <div class="tt-row">Risk Score: <span id="tt-risk-${id}" class="tt-val">0.0</span></div>
          </div>
        `;
        board.appendChild(cell);
      }
    }

    let activeCivilianCount = 30;
    let usingWebsocket = false;

    // --- State and UI Updates ---------------------------------------------
    function updateUIWithState(state) {
      // --- 1. Update Header Telemetry ---
      document.getElementById('sim-tick').innerText = state.tick;
      
      // Format simulation time
      const tod = state.time_of_day;
      const hours = Math.floor(tod);
      const mins = Math.floor((tod - hours) * 60);
      const ampm = hours >= 12 ? 'PM' : 'AM';
      const displayHours = hours % 12 === 0 ? 12 : hours % 12;
      const displayMins = mins < 10 ? '0' + mins : mins;
      document.getElementById('sim-time').innerText = `${displayHours}:${displayMins} ${ampm}`;

      // --- 2. Update Grid Cells ---
      const zonesMap = {};
      state.zones.forEach(z => {
        zonesMap[z.id] = z;
      });

      let civCount = 0;

      for (let r = 0; r < 6; r++) {
        for (let c = 0; c < 6; c++) {
          const id = `${rows[r]}${c}`;
          const zone = zonesMap[id];
          const cell = document.getElementById(`cell-${id}`);
          
          if (!zone) continue;

          cell.className = `zone-cell ${zone.zone_type}`;
          document.getElementById(`badge-${id}`).innerText = zone.zone_type.substring(0, 4);

          // Risk overlay
          const riskContainer = document.getElementById(`risk-${id}`);
          if (zone.risk_score > 0.05) {
            const scorePct = Math.round(zone.risk_score * 100);
            riskContainer.innerHTML = `<span style="color:#f87171">⚠️ ${scorePct}%</span>`;
            const alpha = Math.min(zone.risk_score * 0.7, 0.95);
            cell.style.backgroundColor = `rgba(239, 68, 68, ${alpha})`;
          } else {
            riskContainer.innerHTML = '';
            cell.style.backgroundColor = '';
          }

          if (zone.is_hotspot) {
            cell.classList.add('hotspot');
          } else {
            cell.classList.remove('hotspot');
          }

          document.getElementById(`tt-type-${id}`).innerText = zone.zone_type;
          document.getElementById(`tt-light-${id}`).innerText = zone.lighting.toFixed(2);
          document.getElementById(`tt-pop-${id}`).innerText = zone.population;
          document.getElementById(`tt-pol-${id}`).innerText = zone.police_count;
          document.getElementById(`tt-risk-${id}`).innerText = zone.risk_score.toFixed(4);

          const agentsContainer = document.getElementById(`agents-${id}`);
          agentsContainer.innerHTML = '';
        }
      }

      // --- 3. Render Agent Badges ---
      state.agents.forEach(agent => {
        const container = document.getElementById(`agents-${agent.zone}`);
        if (container) {
          const dot = document.createElement('span');
          dot.className = `agent-dot ${agent.type}`;
          
          let icon = '🚶';
          if (agent.type === 'police') {
            icon = '👮';
            dot.title = `Officer: ${agent.id} (${agent.state})`;
          } else if (agent.type === 'criminal') {
            icon = '🦹';
            dot.title = `Criminal: ${agent.id} (${agent.state})`;
          } else {
            civCount++;
            dot.title = `Civilian: ${agent.id} (${agent.state})`;
          }
          
          dot.innerText = icon;
          container.appendChild(dot);
        }
      });

      activeCivilianCount = civCount;

      // --- 4. Update Crime log Feed ---
      const feed = document.getElementById('log-feed');
      feed.innerHTML = '';
      if (state.crime_events && state.crime_events.length > 0) {
        state.crime_events.forEach(ev => {
          const item = document.createElement('div');
          item.className = `log-item ${ev.caught ? 'caught' : 'crime'}`;
          
          const timeStr = `[${ev.time_of_day.toFixed(2)}]`;
          const caughtBadge = ev.caught ? '🟢 INTERCEPTED' : '🔴 ESCAPED';
          
          item.innerHTML = `
            <span>${timeStr} <b>${ev.type.toUpperCase()}</b> in <b>${ev.zone}</b></span>
            <span>${caughtBadge}</span>
          `;
          feed.appendChild(item);
        });
      } else {
        feed.innerHTML = `<div style="color:var(--text-secondary); text-align:center; padding-top:2rem;">No crime events logged yet.</div>`;
      }
    }

    // --- Metrics Updates --------------------------------------------------
    function updateMetrics(metrics) {
      const mode = metrics.patrol_mode || 'greedy';
      const modeBadge = document.getElementById('patrol-mode-badge');
      modeBadge.innerText = mode.toUpperCase();
      
      document.getElementById('btn-mode-greedy').className = '';
      document.getElementById('btn-mode-ai').className = '';
      document.getElementById('btn-mode-marl').className = '';
      
      if (mode === 'ai') {
        modeBadge.style.color = 'var(--accent-purple)';
        document.getElementById('btn-mode-ai').className = 'primary';
      } else if (mode === 'marl') {
        modeBadge.style.color = 'var(--accent-orange)';
        document.getElementById('btn-mode-marl').className = 'primary';
      } else {
        modeBadge.style.color = 'var(--accent-blue)';
        document.getElementById('btn-mode-greedy').className = 'primary';
      }

      document.getElementById('m-total-crimes').innerText = metrics.total_crimes;
      document.getElementById('m-caught-crimes').innerText = metrics.total_caught;
      
      const catchRate = metrics.catch_rate || 0.0;
      document.getElementById('m-catch-rate').innerText = `${(catchRate * 100).toFixed(1)}%`;
      
      const avgResp = metrics.avg_response_time;
      document.getElementById('m-resp-time').innerText = avgResp ? `${avgResp.toFixed(1)} ticks` : '-- ticks';
      
      const patrolEff = metrics.patrol_efficiency || 0.0;
      document.getElementById('m-patrol-eff').innerText = `${(patrolEff * 100).toFixed(1)}%`;
    }

    // --- ML Reports Updates ------------------------------------------------
    async function updateMLReport() {
      try {
        const res = await fetch('/reports');
        const report = await res.json();
        if (report && !report.error) {
          document.getElementById('ml-reports-card').style.display = 'block';
          document.getElementById('rep-dataset-size').innerText = report.dataset_size;
          
          const buster = `?t=${new Date().getTime()}`;
          document.getElementById('chart-comparison').src = report.charts.model_comparison + buster;
          document.getElementById('chart-importance').src = report.charts.feature_importance + buster;
          document.getElementById('chart-confusion').src = report.charts.confusion_matrix + buster;
          document.getElementById('chart-roc').src = report.charts.roc_curve + buster;
        }
      } catch (err) {
        console.error("Error loading ML report: ", err);
      }
    }

    // --- WebSocket Stream Setup -------------------------------------------
    let ws;
    function connectWS() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/state`;
      
      console.log(`Connecting to WebSocket: ${wsUrl}`);
      ws = new WebSocket(wsUrl);
      
      ws.onopen = function() {
        console.log("WebSocket stream connected successfully!");
        usingWebsocket = true;
      };
      
      ws.onmessage = function(event) {
        try {
          const state = JSON.parse(event.data);
          updateUIWithState(state);
        } catch (err) {
          console.error("Error parsing WS message: ", err);
        }
      };
      
      ws.onclose = function() {
        console.log("WebSocket stream disconnected. Reconnecting in 3s...");
        usingWebsocket = false;
        setTimeout(connectWS, 3000);
      };
      
      ws.onerror = function(err) {
        console.error("WebSocket error: ", err);
        ws.close();
      };
    }

    // --- HTTP Fallback Polling (if WebSocket unavailable) ------------------
    async function pollStateFallback() {
      if (usingWebsocket) return; // skip if streaming via WS
      try {
        const res = await fetch('/state');
        const state = await res.json();
        updateUIWithState(state);
      } catch (err) {
        console.error("Fallback polling error: ", err);
      }
    }

    // --- Regular Telemetry Polling (metrics / report) ----------------------
    async function pollTelemetry() {
      try {
        const res = await fetch('/metrics');
        const metrics = await res.json();
        updateMetrics(metrics);
      } catch (err) {
        console.error("Telemetry polling error: ", err);
      }
    }

    // --- Control Interventions triggers ---------------------------------------
    async function setPatrolMode(mode) {
      await fetch('/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ set_patrol_mode: mode })
      });
      pollTelemetry();
      pollStateFallback();
    }

    async function spawnPolice(count) {
      if (count > 0) {
        await fetch('/scenario', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ add_police: count })
        });
      } else {
        await fetch('/scenario', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ remove_police: Math.abs(count) })
        });
      }
      pollStateFallback();
    }

    async function spawnCivilians(addAmount) {
      const targetCount = activeCivilianCount + addAmount;
      await fetch('/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ set_civilian_count: targetCount })
      });
      pollStateFallback();
    }

    async function resetMetrics() {
      await fetch('/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset_metrics: true })
      });
      pollTelemetry();
      pollStateFallback();
    }

    // Start WebSocket connection
    connectWS();

    // Set polling timers
    setInterval(pollStateFallback, 500); // 500ms fallback for state
    setInterval(pollTelemetry, 1000);     // 1s for metrics
    setInterval(updateMLReport, 5000);     // 5s for ML charts

    // Initial triggers
    pollStateFallback();
    pollTelemetry();
    updateMLReport();
  </script>
</body>
</html>
"""
