"""
train_rl.py — Dedicated training script to build and save RL and MARL patrol models.
Run this script once to generate the 'rl_policy.zip' and 'marl_policy.zip' files.
"""

import os
import sys
import random

# Ensure the backend package root is on sys.path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation.environment import CityEnvironment
from simulation.agents import CivilianAgent, CriminalAgent, PoliceAgent
from simulation.crime_logic import CrimeLog
from optimization.rl_patrol import PatrolRLAgent
from optimization.marl_patrol import MARLCoordinator

def main():
    print("=" * 60)
    print(" SmartCrimeAI — Offline Patrol Policy Trainer")
    print("=" * 60)
    print("[TRAIN] Setting up fast-forward environments...")
    
    # 1. Initialize environment context
    env = CityEnvironment()
    crime_log = CrimeLog()

    # 2. Spawn temporary lists of agents to configure Gym observation shapes
    police = [PoliceAgent(f"train_pol_{i}", "A0", 0, 0) for i in range(4)]
    civs = [CivilianAgent(f"train_civ_{i}", "A0", 0, 0) for i in range(30)]
    crims = [CriminalAgent(f"train_crim_{i}", "A0", 0, 0) for i in range(5)]

    # --- 1. Train Centralized RL Agent ---
    print("\n" + "-" * 50)
    print(" [1/2] Training Centralized RL Agent (Single PPO)")
    print("-" * 50)
    rl_agent = PatrolRLAgent()
    try:
        rl_agent.train(env, police, civs, crims, crime_log, total_timesteps=5000)
        print("[SUCCESS] Centralized RL agent trained and saved successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to train Centralized RL: {e}")

    # --- 2. Train MARL Coordinator ---
    print("\n" + "-" * 50)
    print(" [2/2] Training Multi-Agent Coordinator (IPPO Co-op)")
    print("-" * 50)
    marl_coordinator = MARLCoordinator()
    try:
        marl_coordinator.train(env, police, civs, crims, crime_log, timesteps=8000)
        print("[SUCCESS] Multi-Agent RL coordinator trained and saved successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to train MARL Coordinator: {e}")

    print("\n" + "=" * 60)
    print(" Training Complete! Both 'rl_policy.zip' and 'marl_policy.zip'")
    print(" are now saved in your 'output/' directory.")
    print(" You can now run 'python main.py' and they will load perfectly.")
    print("=" * 60)

if __name__ == "__main__":
    main()
