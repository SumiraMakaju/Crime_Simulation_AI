"""greedy_patrol.py — Greedy patrol route optimizer based on zone risk scores."""

from __future__ import annotations

from typing import Any, Dict, List

from config import GREEDY_ROUTE_LENGTH, HOTSPOT_RISK_THRESHOLD


class GreedyPatrolOptimizer:
    """Assigns patrol routes to police agents by greedily picking the
    highest-risk zones while avoiding overlap on primary assignments."""

    # ── public API ──────────────────────────────────────────────────────

    def optimize(
        self,
        police_agents: List[Any],
        environment: Any,
    ) -> Dict[str, List[str]]:
        """Return ``{agent_id: [zone_id, …]}`` patrol routes.

        Algorithm
        ---------
        1. Sort every zone by *risk_score* descending.
        2. For each police agent (sorted by *agent_id* for determinism):
           a. Assign the highest-risk *unassigned* zone as the **primary**.
           b. Extend the route to ``GREEDY_ROUTE_LENGTH`` by picking the
              highest-risk *unassigned* **adjacent** zones first, then
              falling back to the global top-risk pool.
        3. No two agents share the same primary zone.
        """
        if not police_agents or not environment:
            return {}

        # --- gather and rank zones -------------------------------------------
        all_zones = self._get_sorted_zones(environment)
        if not all_zones:
            return {}

        # Sets for tracking which zones are already taken
        assigned_primary: set[str] = set()
        assigned_any: set[str] = set()

        patrol_routes: Dict[str, List[str]] = {}

        # Sort agents by id for deterministic ordering
        sorted_agents = sorted(police_agents, key=lambda a: a.agent_id)

        for agent in sorted_agents:
            route = self._build_route(
                agent,
                all_zones,
                environment,
                assigned_primary,
                assigned_any,
            )
            patrol_routes[agent.agent_id] = route

        return patrol_routes

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _get_sorted_zones(environment: Any) -> List[Any]:
        """Return all zones sorted by composite score (RF risk + GNN hotspot) descending."""
        zones = [environment.get_zone(zid) for zid in environment.zone_ids]
        # Composite: 70% RF risk_score + 30% GNN hotspot probability
        zones.sort(
            key=lambda z: 0.7 * z.risk_score + 0.3 * getattr(z, 'gnn_hotspot_prob', 0.0),
            reverse=True
        )
        return zones

    def _build_route(
        self,
        agent: Any,
        all_zones: List[Any],
        environment: Any,
        assigned_primary: set[str],
        assigned_any: set[str],
    ) -> List[str]:
        """Build a route of up to ``GREEDY_ROUTE_LENGTH`` zones for *agent*.

        The first element is the primary zone (unique per agent).
        """
        route: List[str] = []

        # --- 1. pick primary zone (highest-risk, not yet a primary) ----------
        primary_zone = None
        for zone in all_zones:
            if zone.zone_id not in assigned_primary:
                primary_zone = zone
                break

        if primary_zone is None:
            # Extremely unlikely: more agents than zones — just pick first zone
            primary_zone = all_zones[0]

        route.append(primary_zone.zone_id)
        assigned_primary.add(primary_zone.zone_id)
        assigned_any.add(primary_zone.zone_id)

        # --- 2. fill route from adjacent high-risk zones ---------------------
        adj_ids = primary_zone.neighbors if hasattr(primary_zone, "neighbors") else []
        if adj_ids:
            adj_zones = [environment.get_zone(zid) for zid in adj_ids]
            adj_zones.sort(key=lambda z: z.risk_score, reverse=True)

            for z in adj_zones:
                if len(route) >= GREEDY_ROUTE_LENGTH:
                    break
                if z.zone_id not in assigned_any:
                    route.append(z.zone_id)
                    assigned_any.add(z.zone_id)

        # --- 3. fall back to global top zones if route is still short --------
        for zone in all_zones:
            if len(route) >= GREEDY_ROUTE_LENGTH:
                break
            if zone.zone_id not in assigned_any:
                route.append(zone.zone_id)
                assigned_any.add(zone.zone_id)

        return route
