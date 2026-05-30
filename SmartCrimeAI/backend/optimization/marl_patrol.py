"""
marl_patrol.py — Multi-Agent Reinforcement Learning patrol coordinator using Independent PPO.
Enables police agents to coordinate dynamically based on local observations and shared policy weights.
Uses an agent-centric localized observation space, ensuring robustness to any dynamic police count.
"""

import os
import math
import random
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO

from config import (
    GRID_ROWS,
    GRID_COLS,
    DEFAULT_CIVILIAN_COUNT,
    DEFAULT_CRIMINAL_COUNT,
    DEFAULT_POLICE_COUNT,
    MARL_TOTAL_TIMESTEPS,
    MARL_POLICY_PATH,
    MARL_REWARD_INTERCEPT,
    MARL_REWARD_MISS,
    MARL_REWARD_OVERLAP,
    MARL_REWARD_COVERAGE,
)

# ─── Agent-Centric Local Gym Environment ──────────────────────────────────────

class MARLPatrolEnv(gym.Env):
    """
    Agent-centric Gym Environment representing the police patrol simulation from the perspective
    of a single focal police officer. Uses parameter sharing to generalize across any police count.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, environment_ref=None, police_ref=None, civilians_ref=None, criminals_ref=None, crime_log_ref=None, model_ref=None):
        super().__init__()
        
        self.num_police = len(police_ref) if police_ref is not None else DEFAULT_POLICE_COUNT
        
        # Local features per agent (fixed dimension = 23):
        # own_zone_risk (1) + own_zone_lighting (1) + own_zone_pop (1) + own_zone_police (1)
        # + neighbor_risks (4) + neighbor_police (4) 
        # + other_police_distances (9 features, padded with 1.0 representing max distance)
        # + tod_sin (1) + tod_cos (1)
        # = 1 + 1 + 1 + 1 + 4 + 4 + 9 + 2 = 23.
        self.features_per_agent = 23
        
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.features_per_agent,),
            dtype=np.float32
        )
        
        # 5 actions: 0 = stay, 1-4 = move to neighbor 0-3
        self.action_space = spaces.Discrete(5)
        
        # References for live execution
        self.live_env = environment_ref
        self.live_police = police_ref
        self.live_civilians = civilians_ref
        self.live_criminals = criminals_ref
        self.live_crime_log = crime_log_ref
        
        # Training state
        self.env = None
        self.police = []
        self.civilians = []
        self.criminals = []
        self.crime_log = None
        
        # Reference to PPO model to simulate other agents during training
        self.model_ref = model_ref
        
        self.max_steps = 200
        self.current_step = 0

    def _get_local_obs(self, agent_idx: int, env, police, tod) -> np.ndarray:
        """Constructs a local observation vector of fixed size (23) for a single police agent."""
        agent = police[agent_idx]
        zone = env.get_zone(agent.zone_id)
        
        # Basic features
        own_risk = zone.risk_score
        own_lighting = zone.lighting
        own_pop = min(zone.population, 20) / 20.0
        own_police = min(zone.police_count, 5) / 5.0
        
        # Neighbor features (up to 4)
        neighbor_risks = []
        neighbor_police = []
        for i in range(4):
            if i < len(zone.neighbors):
                n_zone = env.get_zone(zone.neighbors[i])
                neighbor_risks.append(n_zone.risk_score)
                neighbor_police.append(min(n_zone.police_count, 5) / 5.0)
            else:
                neighbor_risks.append(0.0)
                neighbor_police.append(0.0)
                
        # Manhattan distances to other police agents, padded up to 9 other officers
        distances = []
        for other_idx, other_agent in enumerate(police):
            if other_idx == agent_idx:
                continue
            other_zone = env.get_zone(other_agent.zone_id)
            dist = abs(zone.row - other_zone.row) + abs(zone.col - other_zone.col)
            distances.append(min(dist, 10) / 10.0)
            
        # Pad with 1.0 (max distance) to make observation vector length exactly 23
        while len(distances) < 9:
            distances.append(1.0)
            
        # Clip to exactly 9 if there are more than 10 officers
        distances = distances[:9]
            
        # Time of day diurnal features
        tod_sin = math.sin(tod * math.pi / 12)
        tod_cos = math.cos(tod * math.pi / 12)
        
        obs = [
            own_risk, own_lighting, own_pop, own_police,
            *neighbor_risks, *neighbor_police,
            *distances,
            tod_sin, tod_cos
        ]
        return np.array(obs, dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        
        if self.live_env is None:
            # We are training, instantiate fresh independent simulation objects
            from simulation.environment import CityEnvironment
            from simulation.agents import CivilianAgent, CriminalAgent, PoliceAgent
            from simulation.crime_logic import CrimeLog
            
            self.env = CityEnvironment(rows=GRID_ROWS, cols=GRID_COLS)
            self.crime_log = CrimeLog()
            
            self.police = []
            for i in range(self.num_police):
                zid = random.choice(self.env.zone_ids)
                z = self.env.get_zone(zid)
                z.police_count += 1
                self.police.append(PoliceAgent(f"marl_pol_{i}", zid, z.col, z.row))
                
            self.civilians = []
            for i in range(DEFAULT_CIVILIAN_COUNT):
                zid = random.choice(self.env.zone_ids)
                z = self.env.get_zone(zid)
                z.population += 1
                self.civilians.append(CivilianAgent(f"marl_civ_{i}", zid, z.col, z.row))
                
            self.criminals = []
            for i in range(DEFAULT_CRIMINAL_COUNT):
                zid = random.choice(self.env.zone_ids)
                z = self.env.get_zone(zid)
                self.criminals.append(CriminalAgent(f"marl_crim_{i}", zid, z.col, z.row))
                
        env = self.live_env if self.live_env else self.env
        police = self.live_police if self.live_police else self.police
        tod = env.time_of_day
        
        # Return observation for the focal agent (index 0)
        return self._get_local_obs(0, env, police, tod), {}

    def step(self, action):
        env = self.live_env if self.live_env else self.env
        police = self.live_police if self.live_police else self.police
        civilians = self.live_civilians if self.live_civilians else self.civilians
        criminals = self.live_criminals if self.live_criminals else self.criminals
        crime_log = self.live_crime_log if self.live_crime_log else self.crime_log
        
        # 1. Apply action to the focal agent (index 0)
        focal_agent = police[0]
        focal_zone = env.get_zone(focal_agent.zone_id)
        if action > 0 and (action - 1) < len(focal_zone.neighbors):
            target_zid = focal_zone.neighbors[action - 1]
            target_zone = env.get_zone(target_zid)
            
            focal_zone.police_count = max(0, focal_zone.police_count - 1)
            target_zone.police_count += 1
            
            focal_agent.zone_id = target_zid
            focal_agent.x = random.uniform(target_zone.col * 10, (target_zone.col + 1) * 10)
            focal_agent.z = random.uniform(target_zone.row * 10, (target_zone.row + 1) * 10)
            focal_agent.state = "patrolling"

        # 2. Simulate decisions for other cooperative officers (index > 0)
        # Using current policy (if available) or random choice as baseline
        tod = env.time_of_day
        for i in range(1, len(police)):
            other_agent = police[i]
            other_zone = env.get_zone(other_agent.zone_id)
            
            # Predict action from policy for teammate
            if self.model_ref is not None:
                other_obs = self._get_local_obs(i, env, police, tod)
                act, _ = self.model_ref.predict(other_obs, deterministic=False)
            else:
                act = random.choice([0, 1, 2, 3, 4])
                
            if act > 0 and (act - 1) < len(other_zone.neighbors):
                target_zid = other_zone.neighbors[act - 1]
                target_zone = env.get_zone(target_zid)
                
                other_zone.police_count = max(0, other_zone.police_count - 1)
                target_zone.police_count += 1
                
                other_agent.zone_id = target_zid
                other_agent.x = random.uniform(target_zone.col * 10, (target_zone.col + 1) * 10)
                other_agent.z = random.uniform(target_zone.row * 10, (target_zone.row + 1) * 10)
                other_agent.state = "patrolling"
                
        # 3. Advance simulation by one tick
        env.advance_tick()
        
        # Notify civilians
        crime_events_this_tick = [e for e in crime_log.events if e.tick == env.tick - 1]
        fleeing_counts = {}
        for c in civilians:
            if c.state == "fleeing":
                fleeing_counts[c.zone_id] = fleeing_counts.get(c.zone_id, 0) + 1
                
        for civ in civilians:
            civ.step(env, crime_events_this_tick, fleeing_counts.get(civ.zone_id, 0))
            
        new_crimes = []
        for crim in criminals:
            event = crim.step(env, crime_log)
            if event:
                new_crimes.append(event)
                
        for event in new_crimes:
            event_zone = env.get_zone(event.zone_id)
            if event_zone.police_count > 0:
                crime_log.mark_caught(event.crime_id, response_time=1)
                
        # 4. Calculate local agent reward for focal officer
        reward = 0.0
        focal_current_zone = env.get_zone(focal_agent.zone_id)
        
        # Coverage
        if focal_current_zone.risk_score > 0.5:
            reward += MARL_REWARD_COVERAGE
            
        # Overlap penalty
        if focal_current_zone.police_count > 1:
            reward += MARL_REWARD_OVERLAP
            
        # Intercepts / Misses
        for event in new_crimes:
            if event.zone_id == focal_agent.zone_id:
                if event.caught:
                    reward += MARL_REWARD_INTERCEPT
                else:
                    reward += MARL_REWARD_MISS

        self.current_step += 1
        terminated = self.current_step >= self.max_steps
        truncated = False
        
        obs = self._get_local_obs(0, env, police, env.time_of_day)
        return obs, reward, terminated, truncated, {}

# ─── Multi-Agent RL Coordinator ─────────────────────────────────────────────

class MARLCoordinator:
    """Coordinates Multi-Agent Reinforcement Learning policy training and routing."""
    
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.device = "cuda" if torch_has_gpu() else "cpu"
        self.features_per_agent = 23

    def train(self, environment, police, civilians, criminals, crime_log, timesteps: int = MARL_TOTAL_TIMESTEPS):
        """Trains the shared policy using stable-baselines3 PPO."""
        print(f"[MARLCoordinator] Initializing MARL Patrol Environment on device: {self.device}...")
        
        # Single-agent training environment focused on parameter-sharing
        train_env = MARLPatrolEnv(
            police_ref=police
        )
        
        self.model = PPO(
            "MlpPolicy",
            train_env,
            learning_rate=3e-4,
            n_steps=256,
            batch_size=64,
            n_epochs=5,
            gamma=0.99,
            verbose=1,
            device=self.device
        )
        
        # Inject self-reference to allow environment to query current policy for teammates
        train_env.model_ref = self.model
        
        print(f"[MARLCoordinator] Training shared policy for {timesteps} timesteps...")
        self.model.learn(total_timesteps=timesteps)
        
        self.is_trained = True
        self.save()
        print("[MARLCoordinator] MARL training complete and policy saved!")

    def get_patrol_routes(self, environment, police) -> dict[str, list[str]]:
        """Queries the trained GNN/RL policy to select optimal adjacent steps for all police."""
        if not self.is_trained or self.model is None:
            return {}
            
        env_wrapper = MARLPatrolEnv(
            environment_ref=environment,
            police_ref=police
        )
        
        routes = {}
        tod = environment.time_of_day
        
        # Predict patrol steps individually for each officer using the shared policy network
        for idx, agent in enumerate(police):
            zone = environment.get_zone(agent.zone_id)
            
            # Extract individual local observation vector of fixed size (23)
            obs = env_wrapper._get_local_obs(idx, environment, police, tod)
            
            # Predict action deterministically
            act, _ = self.model.predict(obs, deterministic=True)
            
            route = [agent.zone_id]
            
            # Map action (Discrete 0-4) to neighbor routes
            if act > 0 and (act - 1) < len(zone.neighbors):
                next_zid = zone.neighbors[act - 1]
                route.append(next_zid)
                
                # Fill remaining 2 spots to build a length-4 route (like Greedy mode)
                next_zone = environment.get_zone(next_zid)
                filled = list(next_zone.neighbors)
                random.shuffle(filled)
                for fz in filled:
                    if fz not in route:
                        route.append(fz)
                        if len(route) >= 4:
                            break
            
            # Ensure route is at least 4 zones long
            while len(route) < 4:
                fill_zone = environment.get_zone(route[-1])
                added = False
                for fz in fill_zone.neighbors:
                    if fz not in route:
                        route.append(fz)
                        added = True
                        break
                if not added:
                    route.append(route[-1])
                    
            routes[agent.agent_id] = route
            
        return routes

    def save(self, path: str = MARL_POLICY_PATH) -> None:
        """Saves policy zip."""
        if self.model is not None:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.model.save(path)
            print(f"[MARLCoordinator] Saved MARL policy -> {path}.zip")

    def load(self, path: str = MARL_POLICY_PATH) -> bool:
        """Loads policy zip."""
        zip_path = f"{path}.zip"
        if os.path.isfile(zip_path) or os.path.isfile(path):
            try:
                loaded_model = PPO.load(path, device=self.device)
                
                # Verify observation space shape compatibility
                if hasattr(loaded_model, "observation_space") and loaded_model.observation_space is not None:
                    loaded_obs_shape = loaded_model.observation_space.shape
                    expected_obs_shape = (self.features_per_agent,)
                    if loaded_obs_shape != expected_obs_shape:
                        print(f"[MARLCoordinator] Loaded policy has incompatible observation shape {loaded_obs_shape}, expected {expected_obs_shape}. Discarding.")
                        return False
                
                # Verify action space compatibility
                if hasattr(loaded_model, "action_space") and loaded_model.action_space is not None:
                    if not hasattr(loaded_model.action_space, "n") or loaded_model.action_space.n != 5:
                        print(f"[MARLCoordinator] Loaded policy has incompatible action space. Discarding.")
                        return False

                self.model = loaded_model
                self.is_trained = True
                print(f"[MARLCoordinator] Loaded MARL policy successfully from {path}")
                return True
            except Exception as e:
                print(f"[MARLCoordinator] Failed to load MARL policy: {e}")
                return False
        return False


def torch_has_gpu() -> bool:
    """Helper to check GPU presence in PyTorch."""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False
