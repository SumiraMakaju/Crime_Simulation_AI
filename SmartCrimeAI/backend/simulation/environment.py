"""
environment.py — Grid-based city environment for the crime simulation.

Provides the Zone dataclass and CityEnvironment class that together
represent an N×M zone grid with day/night lighting cycles, population
tracking, police presence tracking, and crime-risk bookkeeping.
"""

import json
import os
import random
import string
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

from config import (
    GRID_ROWS,
    GRID_COLS,
    ZONE_SIZE_UNITS,
    ZONE_TYPE_WEIGHTS,
    TICKS_PER_HOUR,
    START_HOUR,
    NIGHT_START_HOUR,
    NIGHT_END_HOUR,
    NIGHT_LIGHTING_REDUCTION,
    DARK_ZONE_TYPES,
    HISTORICAL_CRIMES_WINDOW,
    HOTSPOT_RISK_THRESHOLD,
    SHARED_DIR,
    ZONE_CONFIG_JSON,
)


@dataclass
class Zone:
    """A single zone (cell) in the city grid."""

    zone_id: str                                       # e.g. "A3"
    zone_type: str                                     # residential | commercial | park | intersection
    lighting: float                                    # 0.0–1.0, modified by day/night cycle
    population: int = 0                                # civilian count in zone
    police_count: int = 0                              # police agent count in zone
    historical_crimes: List[int] = field(default_factory=list)  # rolling window of crime ticks
    risk_score: float = 0.0                            # 0.0–1.0, set by ML predictor each cycle
    is_hotspot: bool = False                           # True when risk_score > threshold
    neighbors: List[str] = field(default_factory=list) # adjacent zone_ids (4-directional)
    row: int = 0
    col: int = 0
    base_lighting: float = 1.0                         # original lighting before night reduction


class CityEnvironment:
    """
    N×M grid of Zone objects that models the simulated city.

    Handles:
    - Zone creation with weighted random type assignment
    - Tick-based simulation clock with time-of-day conversion
    - Day/night lighting transitions
    - Neighbor lookups and aggregate queries
    - Serialisable snapshot for the API layer
    """

    # --------------------------------------------------------------------- #
    #  Construction
    # --------------------------------------------------------------------- #
    def __init__(self, rows: int = GRID_ROWS, cols: int = GRID_COLS) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.tick: int = 0
        self.time_of_day: float = START_HOUR

        # Build the zone grid
        zone_types = list(ZONE_TYPE_WEIGHTS.keys())
        zone_weights = list(ZONE_TYPE_WEIGHTS.values())

        self.zones: Dict[str, Zone] = {}
        self.zone_ids: List[str] = []

        for r in range(rows):
            for c in range(cols):
                zone_id = self._rc_to_id(r, c)
                chosen_type = random.choices(zone_types, weights=zone_weights, k=1)[0]
                base_light = round(random.uniform(0.6, 1.0), 2)
                zone = Zone(
                    zone_id=zone_id,
                    zone_type=chosen_type,
                    lighting=base_light,
                    base_lighting=base_light,
                    row=r,
                    col=c,
                )
                self.zones[zone_id] = zone
                self.zone_ids.append(zone_id)

        # Wire up 4-directional neighbors
        for r in range(rows):
            for c in range(cols):
                zone_id = self._rc_to_id(r, c)
                neighbors: List[str] = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        neighbors.append(self._rc_to_id(nr, nc))
                self.zones[zone_id].neighbors = neighbors

        # Apply initial lighting based on start hour
        self._apply_lighting()

        # Persist zone layout for Unity / shared consumers
        self._write_zone_config()

    # --------------------------------------------------------------------- #
    #  Tick advancement
    # --------------------------------------------------------------------- #
    def advance_tick(self) -> None:
        """Advance the simulation by one tick and update derived state."""
        self.tick += 1
        self.time_of_day = (START_HOUR + self.tick / TICKS_PER_HOUR) % 24.0
        self._apply_lighting()

    # --------------------------------------------------------------------- #
    #  Queries
    # --------------------------------------------------------------------- #
    def get_zone(self, zone_id: str) -> Zone:
        """Return the Zone object for *zone_id*."""
        return self.zones[zone_id]

    def get_snapshot(self) -> dict:
        """
        Return a JSON-serialisable snapshot of the entire environment.
        Suitable for sending to the frontend via the API.
        """
        zone_dicts: Dict[str, dict] = {}
        for zid, zone in self.zones.items():
            zone_dicts[zid] = {
                "zone_id": zone.zone_id,
                "zone_type": zone.zone_type,
                "lighting": round(zone.lighting, 4),
                "population": zone.population,
                "police_count": zone.police_count,
                "historical_crimes_count": len(zone.historical_crimes),
                "risk_score": round(zone.risk_score, 4),
                "is_hotspot": zone.is_hotspot,
                "neighbors": zone.neighbors,
                "row": zone.row,
                "col": zone.col,
                "base_lighting": round(zone.base_lighting, 4),
            }
        return {
            "tick": self.tick,
            "time_of_day": round(self.time_of_day, 4),
            "rows": self.rows,
            "cols": self.cols,
            "zones": zone_dicts,
        }

    def get_neighbor_avg_risk(self, zone_id: str) -> float:
        """Return the mean risk_score of adjacent zones."""
        neighbors = self.zones[zone_id].neighbors
        if not neighbors:
            return 0.0
        return sum(self.zones[n].risk_score for n in neighbors) / len(neighbors)

    def get_neighbor_police_sum(self, zone_id: str) -> int:
        """Return the total police_count across all adjacent zones."""
        return sum(self.zones[n].police_count for n in self.zones[zone_id].neighbors)

    # --------------------------------------------------------------------- #
    #  Internal helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _rc_to_id(row: int, col: int) -> str:
        """Convert (row, col) to a zone ID like 'A3'."""
        return f"{chr(ord('A') + row)}{col}"

    def _is_night(self) -> bool:
        """Return True if current time_of_day falls in the night window."""
        # Night spans across midnight: e.g. 20:00 → 06:00
        return self.time_of_day >= NIGHT_START_HOUR or self.time_of_day < NIGHT_END_HOUR

    def _apply_lighting(self) -> None:
        """
        Apply or remove the night-time lighting penalty.

        During night hours, zones whose type is in DARK_ZONE_TYPES have their
        lighting reduced.  During the day the lighting is restored to
        base_lighting.
        """
        night = self._is_night()
        for zone in self.zones.values():
            if zone.zone_type in DARK_ZONE_TYPES:
                if night:
                    zone.lighting = zone.base_lighting * (1.0 - NIGHT_LIGHTING_REDUCTION)
                else:
                    zone.lighting = zone.base_lighting
            # Update hotspot flag while iterating
            zone.is_hotspot = zone.risk_score > HOTSPOT_RISK_THRESHOLD

    def _write_zone_config(self) -> None:
        """Write the zone layout to *shared/zone_config.json*."""
        os.makedirs(SHARED_DIR, exist_ok=True)

        zones_data: List[dict] = []
        for zone in self.zones.values():
            zones_data.append({
                "zone_id": zone.zone_id,
                "zone_type": zone.zone_type,
                "row": zone.row,
                "col": zone.col,
                "world_x": float(zone.col * ZONE_SIZE_UNITS),
                "world_z": float(zone.row * ZONE_SIZE_UNITS),
                "neighbors": zone.neighbors,
            })

        config_data = {
            "grid_rows": self.rows,
            "grid_cols": self.cols,
            "zone_size_units": ZONE_SIZE_UNITS,
            "zones": zones_data,
        }

        with open(ZONE_CONFIG_JSON, "w", encoding="utf-8") as fh:
            json.dump(config_data, fh, indent=2)

