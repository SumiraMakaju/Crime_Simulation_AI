"""rl_patrol.py — Reinforcement learning patrol optimizer using PPO."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import gymnasium
import numpy as np
from gymnasium import spaces

from config import (
    GREEDY_ROUTE_LENGTH,
    RL_POLICY_PATH,
    RL_REWARD_INTERCEPT,
    RL_REWARD_MISS,
    RL_REWARD_OVERLAP,
    RL_REWARD_SLOW_RESPONSE,
    RL_SLOW_RESPONSE_THRESHOLD,
    RL_TOTAL_TIMESTEPS,
    HOTSPOT_RISK_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────────────────────
# Gymnasium environment
# ─────────────────────────────────────────────────────────────────────────────

class PatrolEnv(gymnasium.Env):
    """Custom Gymnasium environment for patrol-route optimization.

    Observation (per zone, sorted by zone_id):
        [risk_score, normalised_police_count, is_hotspot]
    Action:
        One discrete zone index per police agent (MultiDiscrete).
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        environment: Any,
        police_agents: List[Any],
        civilians: List[Any],
        criminals: List[Any],
        crime_log: Any,
    ) -> None:
        super().__init__()

        self.environment = environment
        self.police_agents = police_agents
        self.civilians = civilians
        self.criminals = criminals
        self.crime_log = crime_log

        self.n_zones: int = len(environment.zone_ids)
        self.n_police: int = len(police_agents)

        # 3 features per zone: risk_score, norm_police_count, is_hotspot
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(self.n_zones * 3,),
            dtype=np.float32,
        )

        # One zone choice per police agent
        self.action_space = spaces.MultiDiscrete([self.n_zones] * self.n_police)

        self.max_steps: int = 200
        self.current_step: int = 0

        # Cache sorted zone ids for deterministic ordering
        self._sorted_zone_ids: List[str] = sorted(environment.zone_ids)

    # ── observation helper ──────────────────────────────────────────────

    def _get_obs(self) -> np.ndarray:
        """Build a flat float32 observation vector."""
        obs: List[float] = []
        for zid in self._sorted_zone_ids:
            zone = self.environment.get_zone(zid)
            obs.append(float(zone.risk_score))
            obs.append(float(zone.police_count) / 5.0)
            obs.append(float(zone.risk_score >= HOTSPOT_RISK_THRESHOLD))
        return np.array(obs, dtype=np.float32)

    # ── Gymnasium API ───────────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        # Reset the simulation clock for a fresh episode
        if hasattr(self.environment, "tick"):
            self.environment.tick = 0
        self.current_step = 0
        return self._get_obs(), {}

    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """Apply zone assignments, simulate one tick, compute reward."""

        # --- 1. apply action: move police to assigned zones ------------------
        zone_assignment_counts: Dict[str, int] = {}
        for i, agent in enumerate(self.police_agents):
            target_idx = int(action[i]) % self.n_zones
            target_zid = self._sorted_zone_ids[target_idx]

            # Update environment police counts
            old_zone = self.environment.get_zone(agent.zone_id)
            if old_zone.police_count > 0:
                old_zone.police_count -= 1

            agent.zone_id = target_zid
            new_zone = self.environment.get_zone(target_zid)
            new_zone.police_count += 1

            zone_assignment_counts[target_zid] = (
                zone_assignment_counts.get(target_zid, 0) + 1
            )

        # --- 2. simulate one tick: civilians then criminals ------------------
        for civ in self.civilians:
            try:
                civ.step(self.environment, [], 0)
            except Exception:
                pass

        crimes_this_tick: List[Any] = []
        for crim in self.criminals:
            try:
                event = crim.step(self.environment, self.crime_log)
                if event:
                    crimes_this_tick.append(event)
            except Exception:
                pass

        # --- 3. compute reward -----------------------------------------------
        reward: float = 0.0

        for event in crimes_this_tick:
            zone = self.environment.get_zone(event.zone_id)
            if zone.police_count > 0:
                reward += RL_REWARD_INTERCEPT
            else:
                reward += RL_REWARD_MISS

        # Overlap penalty: for each zone, penalise pairs of police sharing it
        for count in zone_assignment_counts.values():
            if count > 1:
                # Number of unique pairs: C(count, 2)
                pairs = count * (count - 1) // 2
                reward += RL_REWARD_OVERLAP * pairs

        # Slow-response penalty (use ticks since crime start)
        for event in crimes_this_tick:
            response_ticks = getattr(event, "response_time", 0) or 0
            if response_ticks > RL_SLOW_RESPONSE_THRESHOLD:
                reward += RL_REWARD_SLOW_RESPONSE

        # --- 4. bookkeeping --------------------------------------------------
        self.current_step += 1
        terminated = self.current_step >= self.max_steps

        return self._get_obs(), reward, terminated, False, {}


# ─────────────────────────────────────────────────────────────────────────────
# RL Agent wrapper
# ─────────────────────────────────────────────────────────────────────────────

class PatrolRLAgent:
    """Thin wrapper around a Stable-Baselines3 PPO model for patrol routing."""

    def __init__(self) -> None:
        self.model: Any = None
        self.is_trained: bool = False
        self.device: str = "auto"  # will use GPU if available

    # ── training ────────────────────────────────────────────────────────

    def train(
        self,
        environment: Any,
        police_agents: List[Any],
        civilians: List[Any],
        criminals: List[Any],
        crime_log: Any,
        total_timesteps: int = RL_TOTAL_TIMESTEPS,
    ) -> None:
        """Train a PPO policy from scratch and save it to disk."""
        from stable_baselines3 import PPO  # deferred to keep import light

        env = PatrolEnv(environment, police_agents, civilians, criminals, crime_log)
        self.model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            device=self.device,
        )
        self.model.learn(total_timesteps=total_timesteps)

        # Ensure output directory exists
        policy_dir = os.path.dirname(RL_POLICY_PATH)
        if policy_dir:
            os.makedirs(policy_dir, exist_ok=True)

        self.model.save(RL_POLICY_PATH)
        self.is_trained = True
        print(f"[RL] Policy saved to {RL_POLICY_PATH}")

    # ── loading ─────────────────────────────────────────────────────────

    def load(
        self,
        path: Optional[str] = None,
        expected_obs_shape: Optional[Tuple[int, ...]] = None,
        expected_action_nvec: Optional[List[int]] = None,
    ) -> bool:
        """Attempt to load a previously saved PPO policy.

        Returns ``True`` if a model was loaded successfully, ``False``
        otherwise.
        """
        load_path = path or RL_POLICY_PATH
        zip_path = load_path if load_path.endswith(".zip") else f"{load_path}.zip"

        if not os.path.isfile(zip_path):
            print(f"[RL] No saved policy found at {zip_path}")
            return False

        try:
            from stable_baselines3 import PPO

            loaded_model = PPO.load(load_path, device=self.device)

            # Verify observation space shape compatibility
            if expected_obs_shape is not None:
                if hasattr(loaded_model, "observation_space") and loaded_model.observation_space is not None:
                    loaded_obs_shape = loaded_model.observation_space.shape
                    if loaded_obs_shape != expected_obs_shape:
                        print(f"[RL] Loaded policy has incompatible observation shape {loaded_obs_shape}, expected {expected_obs_shape}. Discarding.")
                        return False

            # Verify action space compatibility
            if expected_action_nvec is not None:
                if hasattr(loaded_model, "action_space") and loaded_model.action_space is not None:
                    if not hasattr(loaded_model.action_space, "nvec"):
                        print(f"[RL] Loaded policy does not have expected MultiDiscrete action space. Discarding.")
                        return False
                    if list(loaded_model.action_space.nvec) != list(expected_action_nvec):
                        print(f"[RL] Loaded policy has incompatible action nvec {list(loaded_model.action_space.nvec)}, expected {list(expected_action_nvec)}. Discarding.")
                        return False

            self.model = loaded_model
            self.is_trained = True
            print(f"[RL] Policy loaded from {load_path}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[RL] Failed to load policy: {exc}")
            return False

    # ── inference ───────────────────────────────────────────────────────

    def get_patrol_routes(
        self,
        environment: Any,
        police_agents: List[Any],
    ) -> Dict[str, List[str]]:
        """Use the trained policy to produce patrol routes.

        Returns ``{agent_id: [zone_id, …]}`` with routes of length
        ``GREEDY_ROUTE_LENGTH`` (single RL zone + neighbouring high-risk
        zones).
        """
        if not self.is_trained or self.model is None:
            return {}

        sorted_zone_ids = sorted(environment.zone_ids)

        # Build observation identical to PatrolEnv._get_obs
        obs: List[float] = []
        for zid in sorted_zone_ids:
            zone = environment.get_zone(zid)
            obs.append(float(zone.risk_score))
            obs.append(float(zone.police_count) / 5.0)
            obs.append(float(zone.risk_score >= HOTSPOT_RISK_THRESHOLD))

        obs_array = np.array(obs, dtype=np.float32)
        action, _ = self.model.predict(obs_array, deterministic=True)

        # Handle potential shape mismatch if police_agents count differs from trained count
        trained_police_count = 1
        if hasattr(action, "ndim") and action.ndim > 0:
            trained_police_count = action.shape[0]
        elif hasattr(action, "__len__"):
            trained_police_count = len(action)
        elif isinstance(action, (np.ndarray, list)):
            trained_police_count = len(action)

        routes: Dict[str, List[str]] = {}
        sorted_agents = sorted(police_agents, key=lambda a: a.agent_id)

        for i, agent in enumerate(sorted_agents):
            if i < trained_police_count:
                # Use the trained PPO policy prediction
                if trained_police_count == 1:
                    val = int(action)
                else:
                    val = int(action[i])
                zone_idx = val % len(sorted_zone_ids)
                primary_zid = sorted_zone_ids[zone_idx]
            else:
                # Fallback for extra police officers dynamically added
                global_sorted = sorted(
                    sorted_zone_ids,
                    key=lambda zid: environment.get_zone(zid).risk_score,
                    reverse=True,
                )
                assigned_primaries = [routes[a.agent_id][0] for a in sorted_agents[:i] if a.agent_id in routes]
                primary_zid = sorted_zone_ids[0]
                for zid in global_sorted:
                    if zid not in assigned_primaries:
                        primary_zid = zid
                        break

            # Extend route to GREEDY_ROUTE_LENGTH with adjacent high-risk zones
            route = [primary_zid]
            primary_zone = environment.get_zone(primary_zid)
            adj_ids = primary_zone.neighbors if hasattr(primary_zone, "neighbors") else []
            if adj_ids:
                adj_zones = [
                    (aid, environment.get_zone(aid).risk_score) for aid in adj_ids
                ]
                adj_zones.sort(key=lambda t: t[1], reverse=True)
                for aid, _ in adj_zones:
                    if len(route) >= GREEDY_ROUTE_LENGTH:
                        break
                    if aid not in route:
                        route.append(aid)

            # If still short, pad from global high-risk zones
            if len(route) < GREEDY_ROUTE_LENGTH:
                global_sorted = sorted(
                    sorted_zone_ids,
                    key=lambda zid: environment.get_zone(zid).risk_score,
                    reverse=True,
                )
                for zid in global_sorted:
                    if len(route) >= GREEDY_ROUTE_LENGTH:
                        break
                    if zid not in route:
                        route.append(zid)

            routes[agent.agent_id] = route

        return routes
