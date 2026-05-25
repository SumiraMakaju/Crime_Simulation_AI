"""
scenario.py — Runtime scenario engine for the crime simulation.

The ScenarioEngine receives configuration dicts (from the API or
automated tests) and mutates the live simulation state accordingly:
spawning/removing agents, adjusting lighting, changing patrol modes, etc.
"""

import random
from typing import Dict, List

from config import (
    GRID_ROWS,
    GRID_COLS,
    TICKS_PER_HOUR,
    START_HOUR,
    ZONE_SIZE_UNITS,
)

from simulation.agents import CivilianAgent, PoliceAgent


def _random_zone_id(environment) -> str:
    """Return a randomly chosen zone_id from the environment."""
    return random.choice(environment.zone_ids)


def _zone_to_rc(zone_id: str):
    """Parse 'A3' -> (row=0, col=3)."""
    return ord(zone_id[0]) - ord("A"), int(zone_id[1:])


class ScenarioEngine:
    """
    Apply scenario mutations to a running simulation.

    Supported config keys
    ---------------------
    - ``add_police``        : int — spawn N new officers
    - ``remove_police``     : int — remove last N officers
    - ``set_lighting``      : dict — per-zone or ``{"all": float}``
    - ``set_patrol_mode``   : str — "ai" | "random" | "greedy"
    - ``set_civilian_count``: int — target civilian population
    - ``time_jump``         : float — target hour (0.0–24.0)
    - ``reset_metrics``     : any — reset the metric logger
    """

    def __init__(
        self,
        environment,
        civilians: list,
        criminals: list,
        police: list,
        crime_log,
        metric_logger,
    ) -> None:
        self.environment = environment
        self.civilians = civilians
        self.criminals = criminals
        self.police = police
        self.crime_log = crime_log
        self.metric_logger = metric_logger
        self.log: List[dict] = []
        self.patrol_mode: str = "greedy"

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #
    def apply(self, config: dict) -> dict:
        """
        Apply every key in *config* and return a summary dict.

        Parameters
        ----------
        config : dict
            Mapping of scenario-change keys to their parameters.

        Returns
        -------
        dict
            ``{"status": "applied", "tick": int, "changes": list}``
        """
        changes: List[str] = []

        if "add_police" in config:
            n = int(config["add_police"])
            self._add_police(n)
            changes.append(f"added {n} police")

        if "remove_police" in config:
            n = int(config["remove_police"])
            self._remove_police(n)
            changes.append(f"removed {n} police")

        if "set_lighting" in config:
            self._set_lighting(config["set_lighting"])
            changes.append("lighting updated")

        if "set_patrol_mode" in config:
            mode = str(config["set_patrol_mode"])
            self.patrol_mode = mode
            self.metric_logger.set_patrol_mode(mode)
            changes.append(f"patrol mode -> {mode}")

        if "set_civilian_count" in config:
            target = int(config["set_civilian_count"])
            self._set_civilian_count(target)
            changes.append(f"civilian count -> {target}")

        if "time_jump" in config:
            target_hour = float(config["time_jump"])
            self._time_jump(target_hour)
            changes.append(f"time jumped to {target_hour:.1f}h")

        if "reset_metrics" in config:
            self.metric_logger.reset()
            changes.append("metrics reset")

        self.log.append({
            "tick": self.environment.tick,
            "config": config,
            "changes": changes,
        })

        return {
            "status": "applied",
            "tick": self.environment.tick,
            "changes": changes,
        }

    # ------------------------------------------------------------------ #
    #  Handlers
    # ------------------------------------------------------------------ #
    def _add_police(self, n: int) -> None:
        """Spawn *n* new PoliceAgent instances at random zones."""
        existing_count = len(self.police)
        for i in range(n):
            zone_id = _random_zone_id(self.environment)
            row, col = _zone_to_rc(zone_id)
            agent = PoliceAgent(
                agent_id=f"police_{existing_count + i}",
                zone_id=zone_id,
                zone_col=col,
                zone_row=row,
            )
            self.police.append(agent)
            self.environment.get_zone(zone_id).police_count += 1

    def _remove_police(self, n: int) -> None:
        """Remove the last *n* police agents and update zone counts."""
        for _ in range(min(n, len(self.police))):
            agent = self.police.pop()
            zone = self.environment.get_zone(agent.zone_id)
            zone.police_count = max(0, zone.police_count - 1)

    def _set_lighting(self, value) -> None:
        """
        Update zone lighting.

        *value* is either:
        - ``{"all": float}`` — set every zone's base_lighting and lighting
        - ``{zone_id: float, ...}`` — set specific zones
        """
        if isinstance(value, dict):
            if "all" in value:
                level = float(value["all"])
                for zone in self.environment.zones.values():
                    zone.base_lighting = level
                    zone.lighting = level
            else:
                for zone_id, level in value.items():
                    level = float(level)
                    zone = self.environment.get_zone(zone_id)
                    zone.base_lighting = level
                    zone.lighting = level

    def _set_civilian_count(self, target: int) -> None:
        """Add or remove civilians to reach *target* count."""
        current = len(self.civilians)
        if target > current:
            for i in range(target - current):
                zone_id = _random_zone_id(self.environment)
                row, col = _zone_to_rc(zone_id)
                agent = CivilianAgent(
                    agent_id=f"civ_{current + i}",
                    zone_id=zone_id,
                    zone_col=col,
                    zone_row=row,
                )
                self.civilians.append(agent)
                self.environment.get_zone(zone_id).population += 1
        elif target < current:
            to_remove = current - target
            for _ in range(to_remove):
                agent = self.civilians.pop()
                zone = self.environment.get_zone(agent.zone_id)
                zone.population = max(0, zone.population - 1)

    def _time_jump(self, target_hour: float) -> None:
        """
        Advance the simulation clock to *target_hour* (0.0–24.0).

        Computes the number of ticks needed and calls ``advance_tick()``
        for each one so that day/night transitions happen correctly.
        """
        current_hour = self.environment.time_of_day
        if target_hour > current_hour:
            hours_ahead = target_hour - current_hour
        else:
            hours_ahead = (24.0 - current_hour) + target_hour
        ticks_needed = int(hours_ahead * TICKS_PER_HOUR)
        for _ in range(ticks_needed):
            self.environment.advance_tick()
