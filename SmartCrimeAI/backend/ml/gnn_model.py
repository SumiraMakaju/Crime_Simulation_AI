"""
gnn_model.py — Spatio-temporal Graph Neural Network crime predictor in pure PyTorch.
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
    """2-Layer Spatio-Temporal Graph Convolutional Network."""
    def __init__(self, in_features: int = 11, hidden: int = GNN_HIDDEN_DIM, out: int = 1):
        super().__init__()
        self.conv1 = GCNLayer(in_features, hidden)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.conv2 = GCNLayer(hidden, out)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, X: torch.Tensor, A_hat: torch.Tensor) -> torch.Tensor:
        # Layer 1
        h = self.conv1(X, A_hat)
        h = self.relu(h)
        h = self.dropout(h)
        # Layer 2
        logits = self.conv2(h, A_hat)
        probs = self.sigmoid(logits)
        return probs

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
        """Groups historical dataset rows by tick and builds sequence of graph states."""
        from config import DATASET_CSV
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
        
        # Group by tick
        ticks = df["tick"].unique()
        
        graph_X = []
        graph_y = []
        N = len(environment.zone_ids)
        cols = _FEATURE_COLUMNS
        
        # Pre-calculate a baseline feature matrix from the environment as safe default
        base_features = torch.zeros((N, len(cols)), dtype=torch.float32)
        from ml.dataset import FeatureExtractor
        for i, zid in enumerate(environment.zone_ids):
            zone = environment.get_zone(zid)
            features_dict = FeatureExtractor.extract(zone, environment)
            for f_idx, col in enumerate(cols):
                base_features[i, f_idx] = float(features_dict[col])
        
        for tick in sorted(ticks):
            tick_df = df[df["tick"] == tick]
            X_tick = base_features.clone()
            
            # Update time of day for this specific tick
            tod = float(tick_df["time_of_day"].iloc[0]) if len(tick_df) > 0 else float(environment.time_of_day)
            X_tick[:, 0] = tod
            
            y_tick = torch.zeros((N, 1), dtype=torch.float32)
            
            for _, row in tick_df.iterrows():
                zid = row["zone_id"]
                if zid in environment.zone_ids:
                    idx = environment.zone_ids.index(zid)
                    # Override features with actual historical values
                    for f_idx, col in enumerate(cols):
                        X_tick[idx, f_idx] = float(row[col])
                    # Set target label
                    y_tick[idx, 0] = float(row["crime_occurred"])
                    
            graph_X.append(X_tick)
            graph_y.append(y_tick)
            
        return graph_X, graph_y


class GNNTrainer:
    """Coordinates CrimeGCN model creation, training, evaluation, and loading."""
    def __init__(self):
        self.model = CrimeGCN(in_features=11, hidden=GNN_HIDDEN_DIM, out=1)
        self.is_trained = False
        self.eval_metrics = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0}
        self.last_train_size = 0

    def train(self, environment, epochs: int = GNN_EPOCHS) -> dict:
        """Trains GCN on historical graph data using BCE Loss and Adam Optimizer."""
        X_graphs, y_graphs = CityGraphBuilder.build_training_data(environment)
        if len(X_graphs) < 5:
            print(f"[GNNTrainer] Too few graph states ({len(X_graphs)}) to train GNN. Skipping.")
            return self.eval_metrics
            
        A_hat = CityGraphBuilder.build_adjacency(environment)
        
        # Train / Test split on graph level (80/20)
        split_idx = int(len(X_graphs) * 0.8)
        X_train, X_test = X_graphs[:split_idx], X_graphs[split_idx:]
        y_train, y_test = y_graphs[:split_idx], y_graphs[split_idx:]
        
        optimizer = optim.Adam(self.model.parameters(), lr=GNN_LR, weight_decay=1e-4)
        criterion = nn.BCELoss()
        
        self.model.train()
        print(f"[GNNTrainer] Training Graph Neural Network for {epochs} epochs on {len(X_train)} graph states...")
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            for X_g, y_g in zip(X_train, y_train):
                optimizer.zero_grad()
                probs = self.model(X_g, A_hat)
                loss = criterion(probs, y_g)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                
        # Evaluation
        self.model.eval()
        all_true = []
        all_proba = []
        
        with torch.no_grad():
            for X_g, y_g in zip(X_test, y_test):
                probs = self.model(X_g, A_hat)
                all_true.extend(y_g.numpy().flatten())
                all_proba.extend(probs.numpy().flatten())
                
        y_true = np.array(all_true)
        y_proba = np.array(all_proba)
        y_pred = (y_proba > 0.3).astype(int)
        
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
            'is_trained': self.is_trained
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
                print(f"[GNNTrainer] CrimeGCN model successfully loaded from {path}")
                return True
            except Exception as e:
                print(f"[GNNTrainer] Failed to load CrimeGCN model: {e}")
                return False
        return False
