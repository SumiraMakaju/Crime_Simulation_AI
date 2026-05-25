"""main.py — Orchestrator: initializes and runs the entire simulation + API."""

from __future__ import annotations

import os
import random
import sys
import threading
import time

# Ensure the backend package root is on sys.path so bare imports work.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Local package imports ───────────────────────────────────────────────────
from simulation.environment import CityEnvironment
from simulation.agents import CivilianAgent, CriminalAgent, PoliceAgent
from simulation.crime_logic import CrimeLog, MetricLogger
from simulation.scenario import ScenarioEngine

from ml.predict import CrimePredictor
from ml.train_model import ModelTrainer
from ml.dataset import load_dataset

from optimization.greedy_patrol import GreedyPatrolOptimizer
from optimization.rl_patrol import PatrolRLAgent

from api.server import create_app, SimulationState

from config import (
    API_HOST,
    API_PORT,
    DATASET_CSV,
    DEFAULT_CIVILIAN_COUNT,
    DEFAULT_CRIMINAL_COUNT,
    DEFAULT_POLICE_COUNT,
    GREEDY_ROUTE_LENGTH,
    GRID_COLS,
    GRID_ROWS,
    MAX_CRIMINAL_LAY_LOW,
    ML_MIN_ROWS,
    PATROL_EFFICIENCY_RISK_THRESHOLD,
    PATROL_UPDATE_INTERVAL,
    PREDICTION_INTERVAL,
    SIMULATION_TICK_SLEEP,
)

import uvicorn


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:  # noqa: C901 — intentionally monolithic orchestrator
    """Bootstrap every subsystem and run the simulation loop forever."""

    # ── 1. Initialise environment ────────────────────────────────────────
    env = CityEnvironment(rows=GRID_ROWS, cols=GRID_COLS)
    print(f"[INIT] City grid created: {GRID_ROWS}×{GRID_COLS} ({len(env.zone_ids)} zones)")

    # ── 2. Spawn agents at random zones ──────────────────────────────────
    zone_ids = list(env.zone_ids)

    civilians = []
    for i in range(DEFAULT_CIVILIAN_COUNT):
        zid = random.choice(zone_ids)
        zone = env.get_zone(zid)
        col = getattr(zone, "col", 0)
        row = getattr(zone, "row", 0)
        civ = CivilianAgent(f"civ_{i}", zid, col, row)
        civilians.append(civ)
        zone.population = getattr(zone, "population", 0) + 1

    criminals = []
    for i in range(DEFAULT_CRIMINAL_COUNT):
        zid = random.choice(zone_ids)
        zone = env.get_zone(zid)
        col = getattr(zone, "col", 0)
        row = getattr(zone, "row", 0)
        crim = CriminalAgent(f"crim_{i}", zid, col, row)
        criminals.append(crim)

    police = []
    for i in range(DEFAULT_POLICE_COUNT):
        zid = random.choice(zone_ids)
        zone = env.get_zone(zid)
        col = getattr(zone, "col", 0)
        row = getattr(zone, "row", 0)
        pol = PoliceAgent(f"pol_{i}", zid, col, row)
        police.append(pol)
        zone.police_count = getattr(zone, "police_count", 0) + 1

    print(
        f"[INIT] Agents spawned — civilians: {len(civilians)}, "
        f"criminals: {len(criminals)}, police: {len(police)}"
    )

    # ── 3. Support objects ───────────────────────────────────────────────
    crime_log = CrimeLog()
    metric_logger = MetricLogger()
    scenario_engine = ScenarioEngine(
        env, civilians, criminals, police, crime_log, metric_logger
    )

    # ── 4. ML pipeline ──────────────────────────────────────────────────
    trainer = ModelTrainer()
    loaded_ml = trainer.load()  # attempt to load saved model
    if loaded_ml:
        print("[INIT] ML model loaded from disk.")
    else:
        print("[INIT] ⚠  No saved ML model found — predictions disabled until enough data is collected.")

    predictor = CrimePredictor()
    predictor.set_trainer(trainer)

    # ── 5. Patrol optimizers ─────────────────────────────────────────────
    greedy_optimizer = GreedyPatrolOptimizer()
    rl_agent = PatrolRLAgent()
    loaded_rl = rl_agent.load()  # attempt to load saved policy
    if loaded_rl:
        print("[INIT] RL patrol policy loaded from disk.")
    else:
        print("[INIT] ⚠  No saved RL policy found — using greedy/random patrol until trained.")

    patrol_routes: dict[str, list[str]] = {}

    # ── 6. Wire up SimulationState and start API server ──────────────────
    sim_state = SimulationState()
    sim_state.environment = env
    sim_state.civilians = civilians
    sim_state.criminals = criminals
    sim_state.police = police
    sim_state.crime_log = crime_log
    sim_state.metric_logger = metric_logger
    sim_state.scenario_engine = scenario_engine
    sim_state.patrol_routes = patrol_routes
    sim_state.predictor = predictor

    app = create_app(sim_state)

    server_thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": API_HOST, "port": API_PORT, "log_level": "info"},
        daemon=True,
    )
    server_thread.start()
    print(f"[INIT] API server started at http://localhost:{API_PORT}")
    print(f"[INIT] API docs at http://localhost:{API_PORT}/docs")

    # ── 7. Main simulation loop ──────────────────────────────────────────
    try:
        while True:
            with sim_state.lock:
                # a. Advance tick
                env.advance_tick()

                # b. Step civilians ───────────────────────────────────────
                # Collect crime events from last tick for awareness
                crime_events_this_tick = [
                    e for e in crime_log.events if getattr(e, "tick", None) == env.tick - 1
                ]

                # Count fleeing civilians per zone (social influence)
                fleeing_counts: dict[str, int] = {}
                for c in civilians:
                    if getattr(c, "state", "") == "fleeing":
                        fleeing_counts[c.zone_id] = fleeing_counts.get(c.zone_id, 0) + 1

                for civ in civilians:
                    civ.step(env, crime_events_this_tick, fleeing_counts.get(civ.zone_id, 0))

                # c. Step criminals ───────────────────────────────────────
                new_crimes: list = []
                for crim in criminals:
                    event = crim.step(env, crime_log)
                    if event:
                        new_crimes.append(event)
                        metric_logger.log_crime(caught=False, response_time=None)

                # d. ML prediction ────────────────────────────────────────
                if env.tick % PREDICTION_INTERVAL == 0 and getattr(predictor, "is_ready", False):
                    try:
                        predictions = predictor.predict_all(env)
                        predictor.update_environment(env, predictions)
                    except Exception as exc:
                        print(f"  [ML] Prediction error: {exc}")

                # e. Patrol optimisation ──────────────────────────────────
                if env.tick % PATROL_UPDATE_INTERVAL == 0:
                    patrol_mode = getattr(scenario_engine, "patrol_mode", "greedy")

                    if patrol_mode == "ai" and rl_agent.is_trained:
                        patrol_routes = rl_agent.get_patrol_routes(env, police)
                    elif patrol_mode == "greedy" or not rl_agent.is_trained:
                        patrol_routes = greedy_optimizer.optimize(police, env)
                    else:  # random fallback
                        patrol_routes = {
                            p.agent_id: random.sample(
                                zone_ids, min(GREEDY_ROUTE_LENGTH, len(zone_ids))
                            )
                            for p in police
                        }

                    # Apply routes to agents
                    for p in police:
                        if p.agent_id in patrol_routes:
                            p.patrol_route = patrol_routes[p.agent_id]
                            p.route_index = 0

                    sim_state.patrol_routes = patrol_routes

                # f. Step police ──────────────────────────────────────────
                for p in police:
                    p.step(env, crime_log)
                    zone = env.get_zone(p.zone_id)
                    metric_logger.log_patrol_tick(
                        zone.risk_score > PATROL_EFFICIENCY_RISK_THRESHOLD
                    )

                # g. Check for caught crimes (immediate intercepts) ────────
                for event in new_crimes:
                    zone = env.get_zone(event.zone_id)
                    if zone.police_count > 0:
                        crime_log.mark_caught(event.crime_id, env.tick - event.tick)
                        # Penalise the criminal who committed the crime
                        for crim in criminals:
                            if crim.zone_id == event.zone_id and getattr(crim, "state", "") != "laying_low":
                                crim.caught_count = getattr(crim, "caught_count", 0) + 1
                                if not hasattr(crim, "hot_zones"):
                                    crim.hot_zones = set()
                                crim.hot_zones.add(event.zone_id)
                                crim.lay_low_timer = MAX_CRIMINAL_LAY_LOW
                                crim.state = "laying_low"
                                break

                # Synchronize metric_logger with all caught events in crime_log
                # This ensures both immediate catches AND responded catches (after travel) are counted!
                caught_events = [e for e in crime_log.events if e.caught]
                if len(caught_events) > metric_logger.total_caught:
                    metric_logger.total_caught = len(caught_events)
                    metric_logger.response_times = [
                        e.response_time for e in caught_events if e.response_time is not None
                    ]
                    # Update mode-specific metrics
                    new_catches = len(caught_events) - sum(
                        metric_logger.mode_counters[m]["caught"] for m in metric_logger.mode_counters
                    )
                    if new_catches > 0:
                        patrol_mode = getattr(scenario_engine, "patrol_mode", "greedy")
                        metric_logger.mode_counters[patrol_mode]["caught"] += new_catches

                # h. Online retrain check ─────────────────────────────────
                dataset_size = len(crime_log.events) * 3  # ~3 CSV rows per crime
                if dataset_size >= ML_MIN_ROWS and trainer.should_retrain(dataset_size):
                    try:
                        X, y = load_dataset(DATASET_CSV)
                        if len(X) >= ML_MIN_ROWS:
                            eval_metrics = trainer.online_retrain(X, y)
                            trainer.save()
                            predictor.set_trainer(trainer)
                            metric_logger.ml_metrics = eval_metrics
                            print(f"  [ML] Retrained on {len(X)} rows. Metrics: {eval_metrics}")
                    except Exception as exc:
                        print(f"  [ML] Retrain error: {exc}")

            # Print status (outside lock)
            recent_events = crime_log.events[-20:] if crime_log.events else []
            active_crimes = len([e for e in recent_events if not getattr(e, "caught", False)])
            total_crimes = getattr(metric_logger, "total_crimes", 0)
            patrol_mode = getattr(scenario_engine, "patrol_mode", "greedy")
            print(
                f"Tick {env.tick:>5} | "
                f"Time {env.time_of_day:05.2f} | "
                f"Active crimes: {active_crimes} | "
                f"Total: {total_crimes} | "
                f"Mode: {patrol_mode}"
            )

            time.sleep(SIMULATION_TICK_SLEEP)

    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        try:
            trainer.save()
        except Exception:
            pass
        print(f"Final metrics: {metric_logger.get_metrics()}")
        print("Goodbye!")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
