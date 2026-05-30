"""
agents.py — Autonomous agent classes for the crime simulation.

Each agent has a ``step()`` method invoked once per simulation tick.

Agent types:
- CivilianAgent:  wanders the city, flees from crime, exhibits social influence
- CriminalAgent:  scouts for opportunity, commits crimes, evades police
- PoliceAgent:    patrols assigned routes, responds to dispatched crimes
"""

import math
import random
import uuid
from typing import Dict, List, Optional, Set

from config import (
    CRIME_MAX_POLICE_CAP,
    CRIME_MAX_POPULATION_CAP,
    CRIME_OPPORTUNITY_THRESHOLD,
    CRIME_TYPES,
    CRIME_WEIGHT_LIGHTING,
    CRIME_WEIGHT_POLICE,
    CRIME_WEIGHT_POPULATION,
    FLEE_DURATION,
    HISTORICAL_CRIMES_WINDOW,
    MAX_CRIMINAL_LAY_LOW,
    POLICE_RESPONSE_WINDOW,
    SOCIAL_INFLUENCE_CHANCE,
    SOCIAL_INFLUENCE_THRESHOLD,
    ZONE_SIZE_UNITS,
)

from simulation.crime_logic import CrimeEvent


# ───────────────────────────────────────────────────────────────────────────── #
#  Helpers
# ───────────────────────────────────────────────────────────────────────────── #

def _zone_to_rc(zone_id: str):
    """Parse a zone ID like 'A3' into (row, col) integers."""
    return ord(zone_id[0]) - ord("A"), int(zone_id[1:])


def _random_pos_in_zone(zone_col: int, zone_row: int):
    """Return a random (x, z) position within the given zone cell."""
    x = zone_col * ZONE_SIZE_UNITS + random.uniform(0, ZONE_SIZE_UNITS)
    z = zone_row * ZONE_SIZE_UNITS + random.uniform(0, ZONE_SIZE_UNITS)
    return x, z


# ───────────────────────────────────────────────────────────────────────────── #
#  CivilianAgent
# ───────────────────────────────────────────────────────────────────────────── #

class CivilianAgent:
    """
    A civilian who wanders the grid, avoids crime-affected zones, and may
    flee due to direct crime exposure or social influence from nearby
    fleeing civilians. Follows a 24-hour diurnal commute schedule.
    """

    def __init__(self, agent_id: str, zone_id: str, zone_col: int, zone_row: int, home_zone_id: Optional[str] = None) -> None:
        self.agent_id: str = agent_id
        self.zone_id: str = zone_id
        self.x: float
        self.z: float
        self.x, self.z = _random_pos_in_zone(zone_col, zone_row)
        self.state: str = "walking"
        self.flee_timer: int = 0
        self.danger_memory: Set[str] = set()
        self.home_zone_id: str = home_zone_id if home_zone_id is not None else zone_id

    @staticmethod
    def _preferred_zone_type(time_of_day: float) -> str:
        """Determines preferred zone type based on the time of day."""
        from config import (
            COMMUTE_MORNING_START,
            COMMUTE_MORNING_END,
            COMMUTE_EVENING_START,
            COMMUTE_EVENING_END,
        )
        if COMMUTE_MORNING_START <= time_of_day < COMMUTE_MORNING_END:
            return "commercial"  # morning commute to work
        elif COMMUTE_MORNING_END <= time_of_day < COMMUTE_EVENING_START:
            return "commercial"  # daytime work hours
        elif COMMUTE_EVENING_START <= time_of_day < COMMUTE_EVENING_END:
            return "residential"  # evening commute home
        else:
            return "residential"  # nighttime home hours

    # ------------------------------------------------------------------ #

    def step(
        self,
        environment,
        crime_events_this_tick: Optional[List] = None,
        fleeing_count_in_zone: int = 0,
    ) -> None:
        """
        Execute one simulation tick for this civilian.

        Parameters
        ----------
        environment : CityEnvironment
        crime_events_this_tick : list[CrimeEvent] | None
            Crimes that occurred this tick (used for proximity flee check).
        fleeing_count_in_zone : int
            How many civilians in the same zone are currently fleeing
            (used for the social-influence mechanic).
        """
        tod = environment.time_of_day

        # Activity weight — peaks near 8 AM and 6 PM, trough near 3 AM
        activity_weight = 0.5 + 0.5 * (math.sin((tod - 3) * math.pi / 12) ** 2)

        # ── 1. Currently fleeing ─────────────────────────────────────────
        if self.flee_timer > 0:
            self.flee_timer -= 1
            self.state = "fleeing"
            return

        # ── 2. Crime nearby? ─────────────────────────────────────────────
        if crime_events_this_tick:
            current_zone = environment.get_zone(self.zone_id)
            nearby_ids = {self.zone_id} | set(current_zone.neighbors)
            for event in crime_events_this_tick:
                if event.zone_id in nearby_ids:
                    self.flee_timer = FLEE_DURATION
                    self.danger_memory.add(event.zone_id)
                    self.state = "fleeing"
                    return

        # ── 3. Social influence ──────────────────────────────────────────
        if (
            fleeing_count_in_zone >= SOCIAL_INFLUENCE_THRESHOLD
            and random.random() < SOCIAL_INFLUENCE_CHANCE
        ):
            self.flee_timer = FLEE_DURATION
            self.state = "fleeing"
            return

        # ── 4. Normal movement ───────────────────────────────────────────
        current_zone = environment.get_zone(self.zone_id)
        neighbors = current_zone.neighbors

        # Prefer zones not in danger_memory
        safe_neighbors = [n for n in neighbors if n not in self.danger_memory]
        if not safe_neighbors:
            safe_neighbors = list(neighbors)  # fallback: pick any

        preferred_type = self._preferred_zone_type(tod)
        from config import SCHEDULE_BIAS_STRENGTH

        # Decide if civilian follows diurnal commute schedule or does active walk
        if random.random() < SCHEDULE_BIAS_STRENGTH and safe_neighbors:
            is_going_home = (tod >= 17.0 or tod < 6.0)
            if is_going_home and self.home_zone_id:
                if self.home_zone_id in safe_neighbors:
                    new_zone_id = self.home_zone_id
                else:
                    # Move towards home zone using Manhattan distance
                    home_row, home_col = _zone_to_rc(self.home_zone_id)
                    best_neighbor = None
                    min_dist = 999.0
                    for n_id in safe_neighbors:
                        nr, nc = _zone_to_rc(n_id)
                        dist = abs(nr - home_row) + abs(nc - home_col)
                        if dist < min_dist:
                            min_dist = dist
                            best_neighbor = n_id
                    new_zone_id = best_neighbor if best_neighbor is not None else self.zone_id
            else:
                # Commuting or working at commercial/intersection zones
                matched = [n for n in safe_neighbors if environment.get_zone(n).zone_type == preferred_type]
                if preferred_type == "commercial":
                    # intersections also act as work/travel areas
                    matched += [n for n in safe_neighbors if environment.get_zone(n).zone_type == "intersection" and n not in matched]
                
                if matched:
                    new_zone_id = random.choice(matched)
                else:
                    # random walk based on activity weight
                    if random.random() < activity_weight:
                        new_zone_id = random.choice(safe_neighbors)
                    else:
                        new_zone_id = self.zone_id
        else:
            # Standard random walk weighted by activity
            if random.random() < activity_weight and safe_neighbors:
                new_zone_id = random.choice(safe_neighbors)
            else:
                new_zone_id = self.zone_id

        # ── 5. Move ──────────────────────────────────────────────────────
        if new_zone_id != self.zone_id:
            old_zone = environment.get_zone(self.zone_id)
            old_zone.population = max(0, old_zone.population - 1)
            new_zone = environment.get_zone(new_zone_id)
            new_zone.population += 1
            self.zone_id = new_zone_id

            new_row, new_col = _zone_to_rc(new_zone_id)
            self.x, self.z = _random_pos_in_zone(new_col, new_row)

        self.state = "walking"


# ───────────────────────────────────────────────────────────────────────────── #
#  CriminalAgent
# ───────────────────────────────────────────────────────────────────────────── #

class CriminalAgent:
    """
    A criminal who scouts zones for opportunity and commits crimes when
    conditions are favourable.  Evades police and lies low after being
    caught.
    """

    def __init__(self, agent_id: str, zone_id: str, zone_col: int, zone_row: int) -> None:
        self.agent_id: str = agent_id
        self.zone_id: str = zone_id
        self.x: float
        self.z: float
        self.x, self.z = _random_pos_in_zone(zone_col, zone_row)
        self.state: str = "scouting"
        self.lay_low_timer: int = 0
        self.hot_zones: Set[str] = set()
        self.safe_zones: Set[str] = set()
        self.caught_count: int = 0

    # ------------------------------------------------------------------ #

    @staticmethod
    def _opportunity_score(zone) -> float:
        """Compute how attractive *zone* is for committing a crime with latent variables and noise."""
        lighting_term = (1.0 - zone.lighting) * CRIME_WEIGHT_LIGHTING
        police_ratio = min(zone.police_count, CRIME_MAX_POLICE_CAP) / CRIME_MAX_POLICE_CAP
        police_term = (1.0 - police_ratio) * CRIME_WEIGHT_POLICE
        pop_ratio = min(zone.population, CRIME_MAX_POPULATION_CAP) / CRIME_MAX_POPULATION_CAP
        population_term = pop_ratio * CRIME_WEIGHT_POPULATION
        
        base_opp = lighting_term + police_term + population_term
        
        # Add latent unobserved crime attractor (Approach 3)
        latent_factor = getattr(zone, "hidden_crime_attractor", 0.0)
        
        # Add dynamic Gaussian noise (Approach 1)
        noise = random.gauss(0, 0.06)
        
        return max(0.0, min(1.0, base_opp + latent_factor + noise))

    # ------------------------------------------------------------------ #

    def step(self, environment, crime_log, total_crimes_ref: Optional[list] = None) -> Optional[CrimeEvent]:
        """
        Execute one simulation tick for this criminal.

        Parameters
        ----------
        environment : CityEnvironment
        crime_log : CrimeLog
        total_crimes_ref : list
            Single-element mutable list ``[int]`` used as a shared counter
            so the criminal can track the global crime count.

        Returns
        -------
        CrimeEvent | None
            The crime event if a crime was committed this tick.
        """
        # ── 1. Laying low ────────────────────────────────────────────────
        if self.lay_low_timer > 0:
            self.lay_low_timer -= 1
            if self.lay_low_timer == 0:
                self.hot_zones.clear()  # Heat has died down, forget hot zones to prevent permanent gridlock
            self.state = "laying_low"
            return None

        zone = environment.get_zone(self.zone_id)

        # ── 2. Police presence → flee ────────────────────────────────────
        police_nearby = zone.police_count > 0 or any(
            environment.get_zone(n).police_count > 0 for n in zone.neighbors
        )
        if police_nearby:
            self.state = "fleeing"
            # Move to the neighbor with the fewest police, preferring not-hot zones
            best_score = float("inf")
            candidates = []
            for n in zone.neighbors:
                nz = environment.get_zone(n)
                score = nz.police_count
                if n in self.hot_zones:
                    score += 100  # heavy penalty
                if score < best_score:
                    best_score = score
                    candidates = [n]
                elif score == best_score:
                    candidates.append(n)
            
            best = random.choice(candidates) if candidates else None
            if best and best != self.zone_id:
                self._move_to(best, environment)
            return None

        # ── 3. Opportunity check ─────────────────────────────────────────
        opp = self._opportunity_score(zone)
        if opp > CRIME_OPPORTUNITY_THRESHOLD and self.zone_id not in self.hot_zones:
            event = self.attempt_crime(environment, crime_log)
            if event is not None and total_crimes_ref is not None:
                total_crimes_ref[0] += 1
            return event

        # ── 4. Move toward best opportunity neighbor ─────────────────────
        best_neighbor = None
        best_opp = -1.0
        for n in zone.neighbors:
            if n in self.hot_zones:
                continue
            n_opp = self._opportunity_score(environment.get_zone(n))
            if n_opp > best_opp:
                best_opp = n_opp
                best_neighbor = n
        if best_neighbor is None and zone.neighbors:
            best_neighbor = random.choice(zone.neighbors)
        if best_neighbor and best_neighbor != self.zone_id:
            self._move_to(best_neighbor, environment)

        self.state = "scouting"
        return None

    # ------------------------------------------------------------------ #

    def attempt_crime(self, environment, crime_log) -> Optional[CrimeEvent]:
        """
        Roll against the opportunity score to determine if a crime occurs.

        Returns the resulting CrimeEvent on success, or None.
        """
        zone = environment.get_zone(self.zone_id)
        opp = self._opportunity_score(zone)

        if random.random() >= opp:
            return None

        # Build feature vector
        feature_vector = {
            "zone_id": zone.zone_id,
            "zone_type": zone.zone_type,
            "lighting": zone.lighting,
            "population": zone.population,
            "police_count": zone.police_count,
            "historical_crimes_count": len(zone.historical_crimes),
            "risk_score": zone.risk_score,
            "neighbor_avg_risk": environment.get_neighbor_avg_risk(self.zone_id),
            "neighbor_police_sum": environment.get_neighbor_police_sum(self.zone_id),
        }

        event = CrimeEvent(
            crime_id=uuid.uuid4().hex,
            zone_id=self.zone_id,
            tick=environment.tick,
            time_of_day=environment.time_of_day,
            feature_vector=feature_vector,
            crime_type=random.choice(CRIME_TYPES),
        )

        # Update zone historical crimes (rolling window)
        zone.historical_crimes.append(environment.tick)
        if len(zone.historical_crimes) > HISTORICAL_CRIMES_WINDOW:
            zone.historical_crimes = zone.historical_crimes[-HISTORICAL_CRIMES_WINDOW:]

        # Persist
        crime_log.append(event, environment)
        self.state = "committing"
        return event

    # ------------------------------------------------------------------ #

    def _move_to(self, new_zone_id: str, environment) -> None:
        """Move to *new_zone_id*, updating environment counts and position."""
        old_zone = environment.get_zone(self.zone_id)
        old_zone.population = max(0, old_zone.population - 1)
        new_zone = environment.get_zone(new_zone_id)
        new_zone.population += 1
        self.zone_id = new_zone_id
        new_row, new_col = _zone_to_rc(new_zone_id)
        self.x, self.z = _random_pos_in_zone(new_col, new_row)


# ───────────────────────────────────────────────────────────────────────────── #
#  PoliceAgent
# ───────────────────────────────────────────────────────────────────────────── #

class PoliceAgent:
    """
    A police officer who patrols a pre-set route and responds to
    dispatched crime events.
    """

    def __init__(self, agent_id: str, zone_id: str, zone_col: int, zone_row: int) -> None:
        self.agent_id: str = agent_id
        self.zone_id: str = zone_id
        self.x: float
        self.z: float
        self.x, self.z = _random_pos_in_zone(zone_col, zone_row)
        self.state: str = "patrolling"
        self.patrol_route: List[str] = []
        self.route_index: int = 0
        self.responding_to: Optional[Dict] = None  # {crime_id, zone_id, tick}
        self.response_log: List[dict] = []

    # ------------------------------------------------------------------ #

    def step(self, environment, crime_log) -> None:
        """
        Execute one simulation tick for this officer.

        Parameters
        ----------
        environment : CityEnvironment
        crime_log : CrimeLog
        """
        # ── 1. Pick up unassigned crime if idle ──────────────────────────
        if self.responding_to is None:
            unassigned = crime_log.get_unassigned_crimes()
            if unassigned:
                target = unassigned[0]
                crime_log.assign_crime(target["crime_id"])
                self.responding_to = {
                    "crime_id": target["crime_id"],
                    "zone_id": target["zone_id"],
                    "tick": target["tick"],
                }
                self.state = "responding"

        # ── 2. Responding to a crime ─────────────────────────────────────
        if self.state == "responding" and self.responding_to is not None:
            target_zone_id = self.responding_to["zone_id"]

            if self.zone_id == target_zone_id:
                # Arrived
                response_time = environment.tick - self.responding_to["tick"]
                self.response_log.append({
                    "crime_id": self.responding_to["crime_id"],
                    "response_time": response_time,
                    "caught": response_time <= POLICE_RESPONSE_WINDOW,
                })
                if response_time <= POLICE_RESPONSE_WINDOW:
                    crime_log.mark_caught(
                        self.responding_to["crime_id"], response_time
                    )
                self.responding_to = None
                self.state = "patrolling"
            else:
                # Check for timeout (give up after 10 ticks)
                elapsed = environment.tick - self.responding_to["tick"]
                if elapsed > 10:
                    self.responding_to = None
                    self.state = "patrolling"
                else:
                    next_zone = self._move_toward(target_zone_id, environment)
                    if next_zone != self.zone_id:
                        self._change_zone(next_zone, environment)
            return

        # ── 3. Patrolling ────────────────────────────────────────────────
        if self.state == "patrolling":
            if not self.patrol_route:
                # No route assigned — stay put
                return
            if self.route_index >= len(self.patrol_route):
                self.route_index = 0
            next_zone = self.patrol_route[self.route_index]
            self.route_index += 1
            if next_zone != self.zone_id:
                self._change_zone(next_zone, environment)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _move_toward(self, target_zone_id: str, environment) -> str:
        """
        Return the neighbouring zone_id that brings us closest to *target*
        (Manhattan distance on the grid).
        """
        tr, tc = _zone_to_rc(target_zone_id)
        current_zone = environment.get_zone(self.zone_id)
        best = self.zone_id
        best_dist = abs(_zone_to_rc(self.zone_id)[0] - tr) + abs(_zone_to_rc(self.zone_id)[1] - tc)

        for n in current_zone.neighbors:
            nr, nc = _zone_to_rc(n)
            dist = abs(nr - tr) + abs(nc - tc)
            if dist < best_dist:
                best_dist = dist
                best = n
        return best

    def _change_zone(self, new_zone_id: str, environment) -> None:
        """Move to *new_zone_id*, updating police counts and position."""
        old_zone = environment.get_zone(self.zone_id)
        old_zone.police_count = max(0, old_zone.police_count - 1)
        new_zone = environment.get_zone(new_zone_id)
        new_zone.police_count += 1
        self.zone_id = new_zone_id
        self._update_position(environment)

    def _update_position(self, environment) -> None:
        """Set x, z to a random point inside the current zone."""
        row, col = _zone_to_rc(self.zone_id)
        self.x, self.z = _random_pos_in_zone(col, row)
