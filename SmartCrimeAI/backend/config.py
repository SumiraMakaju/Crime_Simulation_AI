"""
config.py — Central configuration constants for the Smart Crime AI backend.
All tunable parameters, thresholds, and weights live here.
No magic numbers should appear in any other module.
"""

# ─── Grid Layout ───────────────────────────────────────────────────────────────
GRID_ROWS = 6
GRID_COLS = 6
ZONE_SIZE_UNITS = 10  # Unity world units per zone side

# ─── Simulation Timing ────────────────────────────────────────────────────────
TICKS_PER_HOUR = 12               # 1 tick = 5 simulated minutes
SIMULATION_TICK_SLEEP = 3.0       # seconds of real time per tick (slower, human-readable pace)
START_HOUR = 8.0                  # simulation starts at 8:00 AM

# ─── Agent Counts (defaults) ──────────────────────────────────────────────────
DEFAULT_CIVILIAN_COUNT = 30
DEFAULT_CRIMINAL_COUNT = 5
DEFAULT_POLICE_COUNT = 10

# ─── Zone Type Distribution ───────────────────────────────────────────────────
ZONE_TYPE_WEIGHTS = {
    "residential": 0.40,
    "commercial": 0.25,
    "intersection": 0.20,
    "park": 0.15,
}

# ─── Lighting ──────────────────────────────────────────────────────────────────
NIGHT_START_HOUR = 20.0
NIGHT_END_HOUR = 6.0
NIGHT_LIGHTING_REDUCTION = 0.40   # multiply lighting by (1 - this) at night
DARK_ZONE_TYPES = {"park", "intersection"}  # zones affected by night dimming

# ─── Crime ─────────────────────────────────────────────────────────────────────
CRIME_OPPORTUNITY_THRESHOLD = 0.55
CRIME_TYPES = ["theft", "assault", "vandalism", "burglary"]
HISTORICAL_CRIMES_WINDOW = 20     # rolling window size for zone crime history
POLICE_RESPONSE_WINDOW = 3        # ticks within which police can "catch" criminal

# ─── Criminal Agent Weights (opportunity_score formula) ────────────────────────
CRIME_WEIGHT_LIGHTING = 0.35
CRIME_WEIGHT_POLICE = 0.40
CRIME_WEIGHT_POPULATION = 0.25
CRIME_MAX_POLICE_CAP = 5
CRIME_MAX_POPULATION_CAP = 50
CRIMINAL_REWEIGHT_INTERVAL = 20   # re-weight zone preferences every N total crimes

# ─── Civilian Agent ───────────────────────────────────────────────────────────
FLEE_DURATION = 5                 # ticks a civilian flees after witnessing crime
SOCIAL_INFLUENCE_THRESHOLD = 2    # number of fleeing neighbours to trigger herd flee
SOCIAL_INFLUENCE_CHANCE = 0.60    # probability of herd-flee

# ─── Criminal Agent ───────────────────────────────────────────────────────────
MAX_CRIMINAL_LAY_LOW = 15         # ticks a criminal hides after being caught

# ─── ML ────────────────────────────────────────────────────────────────────────
ML_RETRAIN_INTERVAL = 50          # retrain after this many new crime rows
ML_MIN_ROWS = 100                 # minimum dataset rows before ML kicks in
ML_N_ESTIMATORS = 100             # RandomForest n_estimators
PREDICTION_INTERVAL = 5           # run predictor every N ticks
PATROL_UPDATE_INTERVAL = 5        # re-optimize patrol routes every N ticks

# ─── Hotspot ───────────────────────────────────────────────────────────────────
HOTSPOT_RISK_THRESHOLD = 0.30

# ─── RL ────────────────────────────────────────────────────────────────────────
RL_TOTAL_TIMESTEPS = 5000         # reduced from 50 000 for quick first run
RL_REWARD_INTERCEPT = 10.0
RL_REWARD_MISS = -5.0
RL_REWARD_OVERLAP = -1.0
RL_REWARD_SLOW_RESPONSE = -0.3
RL_SLOW_RESPONSE_THRESHOLD = 5   # ticks

# ─── Patrol Efficiency ────────────────────────────────────────────────────────
PATROL_EFFICIENCY_RISK_THRESHOLD = 0.5

# ─── Greedy Patrol ─────────────────────────────────────────────────────────────
GREEDY_ROUTE_LENGTH = 4           # top-N risk zones per agent route

# ─── Paths (relative to backend/) ─────────────────────────────────────────────
OUTPUT_DIR = "output"
DATASET_CSV = "output/dataset.csv"
SHARED_DIR = "shared"
ZONE_CONFIG_JSON = "shared/zone_config.json"
MODEL_DIR = "output"
MODEL_PATH = "output/crime_model.joblib"
RIDGE_MODEL_PATH = "output/ridge_model.joblib"
RL_POLICY_PATH = "output/rl_policy"

# ─── API ───────────────────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000

# ─── Diurnal Civilian Schedules ────────────────────────────────────────────────
COMMUTE_MORNING_START = 6.0
COMMUTE_MORNING_END = 9.0
COMMUTE_EVENING_START = 17.0
COMMUTE_EVENING_END = 20.0
SCHEDULE_BIAS_STRENGTH = 0.7       # probability of following schedule vs random walk

# ─── Graph Neural Network (GNN) ────────────────────────────────────────────────
GNN_HIDDEN_DIM = 64
GNN_EPOCHS = 50
GNN_LR = 0.001
GNN_MODEL_PATH = "output/gnn_model.pt"
GNN_ENSEMBLE_WEIGHT = 0.0          # GNN disabled in ensemble (RF-only) — GNN still trains for academic comparison
GNN_HOTSPOT_WINDOW = 12            # ticks per prediction window (1 simulated hour)
GNN_HOTSPOT_TOP_PERCENT = 0.20     # top 20% zones by crime count = hotspot

# ─── Multi-Agent Reinforcement Learning (MARL) ─────────────────────────────────
MARL_TOTAL_TIMESTEPS = 8000
MARL_POLICY_PATH = "output/marl_policy"
MARL_REWARD_INTERCEPT = 10.0
MARL_REWARD_MISS = -2.0
MARL_REWARD_OVERLAP = -1.5
MARL_REWARD_COVERAGE = 1.0
