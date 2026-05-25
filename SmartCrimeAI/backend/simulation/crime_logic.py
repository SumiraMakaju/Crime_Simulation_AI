"""
crime_logic.py — Crime event tracking, dataset generation, and metric logging.

Provides:
- CrimeEvent: dataclass for a single crime occurrence
- CrimeLog:   append-only log that also writes training rows to the dataset CSV
- MetricLogger: aggregate counters for simulation-wide KPIs
"""

import csv
import os
import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import (
    CRIME_TYPES,
    DATASET_CSV,
    HISTORICAL_CRIMES_WINDOW,
    OUTPUT_DIR,
)


# ───────────────────────────────────────────────────────────────────────────── #
#  CrimeEvent
# ───────────────────────────────────────────────────────────────────────────── #
@dataclass
class CrimeEvent:
    """Record of a single crime occurrence in the simulation."""

    crime_id: str                              # uuid4 hex string
    zone_id: str
    tick: int
    time_of_day: float
    feature_vector: Dict                       # snapshot of zone features at crime time
    crime_type: str                            # random from CRIME_TYPES
    caught: bool = False
    response_time: Optional[int] = None        # ticks until police arrived, None if uncaught


# ───────────────────────────────────────────────────────────────────────────── #
#  CSV column order (shared between positive and negative rows)
# ───────────────────────────────────────────────────────────────────────────── #
_CSV_COLUMNS = [
    "tick",
    "time_of_day",
    "zone_id",
    "zone_type",
    "lighting",
    "population",
    "police_count",
    "historical_crimes_count",
    "neighbor_avg_risk",
    "neighbor_police_sum",
    "crime_type",
    "crime_occurred",
    "caught",
    "response_time",
]


# ───────────────────────────────────────────────────────────────────────────── #
#  CrimeLog
# ───────────────────────────────────────────────────────────────────────────── #
class CrimeLog:
    """
    Append-only crime log that also writes every event (and negative
    samples) to the dataset CSV consumed by the ML pipeline.
    """

    def __init__(self) -> None:
        self.events: List[CrimeEvent] = []
        self.dispatch_queue: List[dict] = []
        self._csv_initialized: bool = False

    # ------------------------------------------------------------------ #
    #  Core API
    # ------------------------------------------------------------------ #
    def append(self, event: CrimeEvent, environment) -> None:
        """
        Record *event*, enqueue it for dispatch, and persist to CSV.

        Also writes 2 random non-crime zone snapshots (``crime_occurred=0``)
        as negative examples for the training set.
        """
        self.events.append(event)
        self.dispatch_queue.append({
            "crime_id": event.crime_id,
            "zone_id": event.zone_id,
            "tick": event.tick,
            "assigned": False,
        })

        # Positive row
        self._write_csv_row(event, environment, crime_occurred=1)

        # Two negative-sample rows from random zones that had no crime this tick
        other_zones = [
            zid for zid in environment.zone_ids if zid != event.zone_id
        ]
        for neg_zone_id in random.sample(other_zones, min(2, len(other_zones))):
            self._write_negative_row(neg_zone_id, environment)

    def get_recent(self, n: int = 20) -> List[dict]:
        """Return the last *n* events as plain dicts."""
        recent = self.events[-n:]
        return [
            {
                "crime_id": e.crime_id,
                "zone_id": e.zone_id,
                "tick": e.tick,
                "time_of_day": round(e.time_of_day, 4),
                "crime_type": e.crime_type,
                "caught": e.caught,
                "response_time": e.response_time,
            }
            for e in recent
        ]

    def get_unassigned_crimes(self) -> List[dict]:
        """Return dispatch-queue entries that have not been assigned yet."""
        return [d for d in self.dispatch_queue if not d["assigned"]]

    def assign_crime(self, crime_id: str) -> None:
        """Mark a queued crime as assigned to a responding officer."""
        for entry in self.dispatch_queue:
            if entry["crime_id"] == crime_id:
                entry["assigned"] = True
                return

    def mark_caught(self, crime_id: str, response_time: int) -> None:
        """Flag a crime as caught and record the response time."""
        for event in self.events:
            if event.crime_id == crime_id:
                event.caught = True
                event.response_time = response_time
                return

    # ------------------------------------------------------------------ #
    #  CSV helpers
    # ------------------------------------------------------------------ #
    def _ensure_csv(self) -> None:
        """Create the output directory and write the CSV header if needed."""
        if self._csv_initialized:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if not os.path.exists(DATASET_CSV):
            with open(DATASET_CSV, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(_CSV_COLUMNS)
        self._csv_initialized = True

    def _write_csv_row(self, event: CrimeEvent, environment, crime_occurred: int) -> None:
        """Append one row to the dataset CSV for a crime event."""
        self._ensure_csv()
        zone = environment.get_zone(event.zone_id)
        row = [
            event.tick,
            round(event.time_of_day, 4),
            event.zone_id,
            zone.zone_type,
            round(zone.lighting, 4),
            zone.population,
            zone.police_count,
            len(zone.historical_crimes),
            round(environment.get_neighbor_avg_risk(event.zone_id), 4),
            environment.get_neighbor_police_sum(event.zone_id),
            event.crime_type,
            crime_occurred,
            int(event.caught),
            event.response_time if event.response_time is not None else "",
        ]
        with open(DATASET_CSV, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(row)

    def _write_negative_row(self, zone_id: str, environment) -> None:
        """Write a non-crime (negative) sample row to the dataset CSV."""
        self._ensure_csv()
        zone = environment.get_zone(zone_id)
        row = [
            environment.tick,
            round(environment.time_of_day, 4),
            zone_id,
            zone.zone_type,
            round(zone.lighting, 4),
            zone.population,
            zone.police_count,
            len(zone.historical_crimes),
            round(environment.get_neighbor_avg_risk(zone_id), 4),
            environment.get_neighbor_police_sum(zone_id),
            "",   # crime_type — not applicable
            0,    # crime_occurred
            0,    # caught
            "",   # response_time
        ]
        with open(DATASET_CSV, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(row)


# ───────────────────────────────────────────────────────────────────────────── #
#  MetricLogger
# ───────────────────────────────────────────────────────────────────────────── #
class MetricLogger:
    """Aggregate simulation-wide metrics for the dashboard API."""

    def __init__(self) -> None:
        self.total_crimes: int = 0
        self.total_caught: int = 0
        self.response_times: List[int] = []
        self.patrol_mode: str = "greedy"
        self.mode_counters: Dict[str, Dict[str, int]] = {
            "ai": {"crimes": 0, "caught": 0},
            "random": {"crimes": 0, "caught": 0},
            "greedy": {"crimes": 0, "caught": 0},
        }
        self.patrol_ticks_in_risk_zones: int = 0
        self.patrol_total_ticks: int = 0
        self.ml_metrics: dict = {}

    # ------------------------------------------------------------------ #
    #  Logging
    # ------------------------------------------------------------------ #
    def log_crime(self, caught: bool, response_time: Optional[int] = None) -> None:
        """Record a single crime event against the counters."""
        self.total_crimes += 1
        self.mode_counters[self.patrol_mode]["crimes"] += 1
        if caught:
            self.total_caught += 1
            self.mode_counters[self.patrol_mode]["caught"] += 1
            if response_time is not None:
                self.response_times.append(response_time)

    def log_patrol_tick(self, in_risk_zone: bool) -> None:
        """Track patrol efficiency (time spent in high-risk zones)."""
        self.patrol_total_ticks += 1
        if in_risk_zone:
            self.patrol_ticks_in_risk_zones += 1

    def set_patrol_mode(self, mode: str) -> None:
        """Switch the current patrol mode label (ai | random | greedy)."""
        self.patrol_mode = mode

    # ------------------------------------------------------------------ #
    #  Reporting
    # ------------------------------------------------------------------ #
    def get_metrics(self) -> dict:
        """Return a snapshot of all tracked metrics."""
        catch_rate = (
            self.total_caught / self.total_crimes if self.total_crimes else 0.0
        )
        avg_response = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times
            else 0.0
        )
        patrol_efficiency = (
            self.patrol_ticks_in_risk_zones / self.patrol_total_ticks
            if self.patrol_total_ticks
            else 0.0
        )
        return {
            "total_crimes": self.total_crimes,
            "total_caught": self.total_caught,
            "catch_rate": round(catch_rate, 4),
            "avg_response_time": round(avg_response, 4),
            "patrol_efficiency": round(patrol_efficiency, 4),
            "patrol_mode": self.patrol_mode,
            "ml_metrics": self.ml_metrics,
            "mode_counters": self.mode_counters,
        }

    def reset(self) -> None:
        """Clear all counters back to zero."""
        self.total_crimes = 0
        self.total_caught = 0
        self.response_times.clear()
        self.patrol_ticks_in_risk_zones = 0
        self.patrol_total_ticks = 0
        self.ml_metrics = {}
        for mode in self.mode_counters:
            self.mode_counters[mode] = {"crimes": 0, "caught": 0}
