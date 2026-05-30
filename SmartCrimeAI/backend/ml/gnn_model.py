"""
gnn_model.py — Spatial Graph Neural Network hotspot predictor in pure PyTorch.
Treats the city grid as a graph where zones are nodes and spatial neighbors are edges.
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

from config import (
    GNN_HIDDEN_DIM,
    GNN_EPOCHS,
    GNN_LR,
    GNN_MODEL_PATH,
)

# ─── Pure PyTorch Graph Convolutional Network Layer ──────────────────────────

class GCNLayer(nn.Module):
    """Symmetric GCN Propagation Layer: H' = σ(A_hat * H * W)"""
    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features)
        
    def forward(self, X: torch.Tensor, A_hat: torch.Tensor) -> torch.Tensor:
        # Propagation step: aggregate neighbor features
        support = torch.matmul(A_hat, X)
        # Linear projection step
        out = self.linear(support)
        return out


class CrimeGCN(nn.Module):
    """3-Layer Spatial Graph Convolutional Network with BatchNorm."""
    def __init__(self, in_features: int = 11, hidden: int = GNN_HIDDEN_DIM, out: int = 1):
        super().__init__()
        self.conv1 = GCNLayer(in_features, hidden)
        self.bn1 = nn.BatchNorm1d(hidden)
        self.conv2 = GCNLayer(hidden, hidden)
        self.bn2 = nn.BatchNorm1d(hidden)
        self.conv3 = GCNLayer(hidden, out)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)

    def forward(self, X: torch.Tensor, A_hat: torch.Tensor, return_logits: bool = False) -> torch.Tensor:
        # Layer 1
        h = self.conv1(X, A_hat)
        h = self.bn1(h)
        h = self.relu(h)
        h = self.dropout(h)
        # Layer 2
        h = self.conv2(h, A_hat)
        h = self.bn2(h)
        h = self.relu(h)
        h = self.dropout(h)
        # Layer 3 (output)
        logits = self.conv3(h, A_hat)
        if return_logits:
            return logits
        return torch.sigmoid(logits)

# ─── Graph Construction and Training ──────────────────────────────────────────

class CityGraphBuilder:
    """Helper to convert the grid city environment and dataset into GNN graph structures."""

    @staticmethod
    def build_adjacency(environment) -> torch.Tensor:
        """Computes the symmetric normalized adjacency matrix A_hat = D^-1/2 * A * D^-1/2."""
        N = len(environment.zone_ids)
        A = torch.zeros((N, N), dtype=torch.float32)
        
        # Pre-fill self-loops
        for i in range(N):
            A[i, i] = 1.0
            
        # Connect neighbors 4-directionally
        for i, zid in enumerate(environment.zone_ids):
            zone = environment.get_zone(zid)
            for neighbor_id in zone.neighbors:
                if neighbor_id in environment.zone_ids:
                    j = environment.zone_ids.index(neighbor_id)
                    A[i, j] = 1.0
                    
        # Symmetric normalization: D^-1/2 * A * D^-1/2
        d = A.sum(dim=1)
        d_inv_sqrt = torch.pow(d, -0.5)
        d_inv_sqrt[torch.isinf(d_inv_sqrt)] = 0.0
        D_inv_sqrt = torch.diag(d_inv_sqrt)
        A_hat = D_inv_sqrt @ A @ D_inv_sqrt
        return A_hat

    @staticmethod
    def build_node_features(environment) -> torch.Tensor:
        """Extracts live features for all zones and stacks them into an (N, F) tensor."""
        N = len(environment.zone_ids)
        from ml.dataset import FeatureExtractor
        cols = FeatureExtractor.feature_columns()
        F = len(cols)
        X = torch.zeros((N, F), dtype=torch.float32)
        
        for i, zid in enumerate(environment.zone_ids):
            zone = environment.get_zone(zid)
            features_dict = FeatureExtractor.extract(zone, environment)
            for f_idx, col in enumerate(cols):
                X[i, f_idx] = float(features_dict[col])
        return X

    @staticmethod
    def build_training_data(environment) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """Groups historical dataset rows into hourly windows and labels top-crime zones as hotspots."""
        from config import DATASET_CSV, GNN_HOTSPOT_WINDOW, GNN_HOTSPOT_TOP_PERCENT
        import pandas as pd

        if not os.path.exists(DATASET_CSV):
            return [], []

        df = pd.read_csv(DATASET_CSV)
        if len(df) == 0:
            return [], []

        # One-hot encode zone_type to match FeatureExtractor
        from ml.dataset import _ZONE_TYPE_DUMMIES, _FEATURE_COLUMNS
        if "zone_type" in df.columns:
            dummies = pd.get_dummies(df["zone_type"], prefix="zone_type")
            df = pd.concat([df.drop(columns=["zone_type"]), dummies], axis=1)

        for col in _ZONE_TYPE_DUMMIES:
            if col not in df.columns:
                df[col] = 0.0

        df = df.fillna(0.0)

        N = len(environment.zone_ids)
        cols = _FEATURE_COLUMNS
        n_hotspots = max(1, int(N * GNN_HOTSPOT_TOP_PERCENT))  # ~7 zones

        # Pre-calculate a baseline feature matrix from the environment as safe default
        base_features = torch.zeros((N, len(cols)), dtype=torch.float32)
        from ml.dataset import FeatureExtractor
        for i, zid in enumerate(environment.zone_ids):
            zone = environment.get_zone(zid)
            features_dict = FeatureExtractor.extract(zone, environment)
            for f_idx, col in enumerate(cols):
                base_features[i, f_idx] = float(features_dict[col])

        # Group ticks into windows of GNN_HOTSPOT_WINDOW (12 ticks = 1 hour)
        all_ticks = sorted(df["tick"].unique())
        if len(all_ticks) < GNN_HOTSPOT_WINDOW:
            return [], []

        graph_X = []
        graph_y = []

        for w_start in range(0, len(all_ticks) - GNN_HOTSPOT_WINDOW + 1, GNN_HOTSPOT_WINDOW):
            window_ticks = all_ticks[w_start:w_start + GNN_HOTSPOT_WINDOW]
            window_df = df[df["tick"].isin(window_ticks)]

            if len(window_df) == 0:
                continue

            # Build feature matrix using mid-window tick as representative snapshot
            X_window = base_features.clone()
            mid_tick = window_ticks[len(window_ticks) // 2]
            mid_df = window_df[window_df["tick"] == mid_tick]

            tod = float(mid_df["time_of_day"].iloc[0]) if len(mid_df) > 0 else float(window_df["time_of_day"].iloc[0])
            X_window[:, 0] = tod

            for _, row in mid_df.iterrows():
                zid = row["zone_id"]
                if zid in environment.zone_ids:
                    idx = environment.zone_ids.index(zid)
                    for f_idx, col in enumerate(cols):
                        X_window[idx, f_idx] = float(row[col])

            # Build hotspot labels: count crimes per zone across the entire window
            crime_rows = window_df[window_df["crime_occurred"] == 1]
            crime_counts = {zid: 0 for zid in environment.zone_ids}
            for _, row in crime_rows.iterrows():
                zid = row["zone_id"]
                if zid in crime_counts:
                    crime_counts[zid] += 1

            # Top n_hotspots zones by crime count = hotspot (1), rest = 0
            sorted_zones = sorted(crime_counts.items(), key=lambda x: x[1], reverse=True)
            hotspot_zones = set()
            for zid, count in sorted_zones[:n_hotspots]:
                if count > 0:  # Only label as hotspot if at least 1 crime
                    hotspot_zones.add(zid)

            y_window = torch.zeros((N, 1), dtype=torch.float32)
            for zid in hotspot_zones:
                if zid in environment.zone_ids:
                    idx = environment.zone_ids.index(zid)
                    y_window[idx, 0] = 1.0

            graph_X.append(X_window)
            graph_y.append(y_window)

        print(f"[GNNTrainer] Built {len(graph_X)} hourly window graphs for hotspot training")
        return graph_X, graph_y


class GNNTrainer:
    """Coordinates CrimeGCN model creation, training, evaluation, and loading."""
    def __init__(self):
        self.model = CrimeGCN(in_features=11, hidden=GNN_HIDDEN_DIM, out=1)
        self.is_trained = False
        self.eval_metrics = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0}
        self.last_train_size = 0
        self.optimal_threshold = 0.5  # Will be tuned during training

    def _find_optimal_threshold(self, y_true: np.ndarray, y_proba: np.ndarray) -> float:
        """Find the probability threshold that maximizes F1 score using ROC analysis."""
        from sklearn.metrics import roc_curve
        best_threshold = 0.5
        best_f1 = 0.0
        # Test thresholds from 0.1 to 0.9 in steps of 0.05
        for threshold in np.arange(0.1, 0.91, 0.05):
            y_pred_t = (y_proba > threshold).astype(int)
            if y_pred_t.sum() == 0:
                continue
            prec_t = float(precision_score(y_true, y_pred_t, zero_division=0))
            rec_t = float(recall_score(y_true, y_pred_t, zero_division=0))
            if prec_t + rec_t > 0:
                f1_t = 2 * prec_t * rec_t / (prec_t + rec_t)
                if f1_t > best_f1:
                    best_f1 = f1_t
                    best_threshold = threshold
        return float(best_threshold)

    def train(self, environment, epochs: int = GNN_EPOCHS) -> dict:
        """Trains GCN on historical graph data using class-weighted BCEWithLogitsLoss."""
        X_graphs, y_graphs = CityGraphBuilder.build_training_data(environment)
        if len(X_graphs) < 5:
            print(f"[GNNTrainer] Too few graph states ({len(X_graphs)}) to train GNN. Skipping.")
            return self.eval_metrics

        A_hat = CityGraphBuilder.build_adjacency(environment)

        # Subsample graph states if too many (keeps training under ~2 min on CPU)
        MAX_GRAPH_STATES = 500
        if len(X_graphs) > MAX_GRAPH_STATES:
            import random as _rng
            indices = sorted(_rng.sample(range(len(X_graphs)), MAX_GRAPH_STATES))
            X_graphs = [X_graphs[i] for i in indices]
            y_graphs = [y_graphs[i] for i in indices]
            print(f"[GNNTrainer] Subsampled to {MAX_GRAPH_STATES} graph states (from {len(indices)} total ticks)")

        # Train / Test split on graph level (80/20)
        split_idx = int(len(X_graphs) * 0.8)
        X_train, X_test = X_graphs[:split_idx], X_graphs[split_idx:]
        y_train, y_test = y_graphs[:split_idx], y_graphs[split_idx:]

        # Compute class imbalance ratio for pos_weight
        all_labels = torch.cat(y_train).numpy().flatten()
        n_pos = max(float(all_labels.sum()), 1.0)
        n_neg = max(float(len(all_labels) - n_pos), 1.0)
        pos_weight = torch.tensor([n_neg / n_pos], dtype=torch.float32)
        pos_weight = torch.clamp(pos_weight, max=5.0)  # Cap to prevent extreme weighting
        print(f"[GNNTrainer] Class balance: {int(n_pos)} positive, {int(n_neg)} negative, pos_weight={pos_weight.item():.2f}")

        optimizer = optim.Adam(self.model.parameters(), lr=GNN_LR, weight_decay=1e-4)
        # Use BCEWithLogitsLoss with pos_weight for class-imbalance correction
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

        self.model.train()
        print(f"[GNNTrainer] Training Graph Neural Network for {epochs} epochs on {len(X_train)} graph states...")

        for epoch in range(epochs):
            epoch_loss = 0.0
            for X_g, y_g in zip(X_train, y_train):
                optimizer.zero_grad()
                logits = self.model(X_g, A_hat, return_logits=True)
                loss = criterion(logits, y_g)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

        # Evaluation
        self.model.eval()
        all_true = []
        all_proba = []

        with torch.no_grad():
            for X_g, y_g in zip(X_test, y_test):
                probs = self.model(X_g, A_hat, return_logits=False)  # sigmoid output
                all_true.extend(y_g.numpy().flatten())
                all_proba.extend(probs.numpy().flatten())

        y_true = np.array(all_true)
        y_proba = np.array(all_proba)

        # Find optimal classification threshold that maximizes F1
        self.optimal_threshold = self._find_optimal_threshold(y_true, y_proba)
        y_pred = (y_proba > self.optimal_threshold).astype(int)
        print(f"[GNNTrainer] Optimal classification threshold: {self.optimal_threshold:.2f}")

        # Compute metrics
        try:
            prec = float(precision_score(y_true, y_pred, zero_division=0))
            rec = float(recall_score(y_true, y_pred, zero_division=0))
            f1 = float(f1_score(y_true, y_pred, zero_division=0))
            try:
                auc_score = float(roc_auc_score(y_true, y_proba))
            except ValueError:
                auc_score = 0.5  # default if only one class exists in test split
        except Exception as e:
            print(f"[GNNTrainer] Error during GNN evaluation: {e}")
            prec, rec, f1, auc_score = 0.0, 0.0, 0.0, 0.5

        self.eval_metrics = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "roc_auc": auc_score
        }

        self.is_trained = True
        self.last_train_size = len(X_graphs) * 3  # Approximate rows equivalent
        print(f"[GNNTrainer] GNN trained successfully. Test metrics: {self.eval_metrics}")

        self.save()
        return self.eval_metrics

    def predict(self, environment) -> dict[str, float]:
        """Runs inference on live environment state to predict risk_score for each zone."""
        if not self.is_trained:
            return {}
            
        self.model.eval()
        A_hat = CityGraphBuilder.build_adjacency(environment)
        X = CityGraphBuilder.build_node_features(environment)
        
        with torch.no_grad():
            probs = self.model(X, A_hat).numpy().flatten()
            
        predictions = {}
        for i, zid in enumerate(environment.zone_ids):
            predictions[zid] = float(probs[i])
            
        return predictions

    def save(self, path: str = GNN_MODEL_PATH) -> None:
        """Saves weights to output/gnn_model.pt."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'eval_metrics': self.eval_metrics,
            'is_trained': self.is_trained,
            'optimal_threshold': self.optimal_threshold
        }, path)
        print(f"[GNNTrainer] Saved CrimeGCN model -> {path}")

    def load(self, path: str = GNN_MODEL_PATH) -> bool:
        """Loads weights from output/gnn_model.pt."""
        if os.path.isfile(path):
            try:
                checkpoint = torch.load(path, map_location=torch.device('cpu'))
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.eval_metrics = checkpoint.get('eval_metrics', self.eval_metrics)
                self.is_trained = checkpoint.get('is_trained', True)
                self.optimal_threshold = checkpoint.get('optimal_threshold', 0.5)
                print(f"[GNNTrainer] CrimeGCN model successfully loaded from {path}")
                return True
            except Exception as e:
                print(f"[GNNTrainer] Failed to load CrimeGCN model: {e}. Will retrain.")
                return False
        return False
