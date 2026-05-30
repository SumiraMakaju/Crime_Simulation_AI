"""predict.py — Crime risk prediction using trained ML models."""

import numpy as np
import pandas as pd

from config import HOTSPOT_RISK_THRESHOLD, MODEL_PATH
from ml.dataset import FeatureExtractor
from ml.train_model import ModelTrainer
from ml.gnn_model import GNNTrainer


class CrimePredictor:
    """High-level facade that wires together :class:`ModelTrainer`,
    :class:`GNNTrainer`, and :class:`FeatureExtractor` to produce
    ensemble per-zone crime risk predictions.
    """

    def __init__(self) -> None:
        self.trainer: ModelTrainer | None = None
        self.gnn_trainer: GNNTrainer | None = None
        self.extractor: FeatureExtractor = FeatureExtractor()
        self.is_ready: bool = False

    # ------------------------------------------------------------------ #
    #  Model loading / injection                                           #
    # ------------------------------------------------------------------ #
    def load(self, path: str | None = None) -> bool:
        """Create a :class:`ModelTrainer` and attempt to load persisted
        models from disk.

        Parameters
        ----------
        path : str | None
            Optional override for the classifier file path.

        Returns
        -------
        bool
            ``True`` if models were loaded and the predictor is ready.
        """
        self.trainer = ModelTrainer()
        loaded = self.trainer.load(path)
        self.is_ready = loaded
        
        # Load GNN if available
        self.gnn_trainer = GNNTrainer()
        gnn_loaded = self.gnn_trainer.load()
        
        return self.is_ready

    def set_trainer(self, trainer: ModelTrainer) -> None:
        """Inject an already-trained :class:`ModelTrainer`.

        Parameters
        ----------
        trainer : ModelTrainer
            A trainer instance (usually freshly trained or retrained).
        """
        self.trainer = trainer
        self.is_ready = trainer.is_trained

    def set_gnn_trainer(self, gnn_trainer: GNNTrainer) -> None:
        """Inject an already-trained :class:`GNNTrainer`."""
        self.gnn_trainer = gnn_trainer

    # ------------------------------------------------------------------ #
    #  Prediction                                                          #
    # ------------------------------------------------------------------ #
    def predict_all(self, environment) -> dict:
        """Predict crime risk for every zone in *environment*.

        Parameters
        ----------
        environment : object
            Must expose ``zones`` (iterable of zone objects) and the
            helper methods expected by :class:`FeatureExtractor`.

        Returns
        -------
        dict
            ``{zone_id: {"risk_score": float, "is_hotspot": bool,
            "predicted_crime_window": int}}``
            Empty dict if the predictor is not ready.
        """
        if not self.is_ready or self.trainer is None:
            return {}

        columns = self.extractor.feature_columns()
        results: dict = {}

        # GNN hotspot predictions if available (separate from RF ensemble)
        gnn_preds = {}
        if self.gnn_trainer and self.gnn_trainer.is_trained:
            try:
                gnn_preds = self.gnn_trainer.predict(environment)
            except Exception as e:
                print(f"[CrimePredictor] GNN prediction error: {e}")

        for zone in environment.zones.values():
            features = self.extractor.extract(zone, environment)

            # Build a single-row DataFrame in canonical column order
            row = pd.DataFrame([features], columns=columns)

            # Probability of crime (class = 1) from Random Forest
            proba = self.trainer.classifier.predict_proba(row)
            # predict_proba returns shape (1, n_classes); class-1 is last col
            rf_score = float(proba[0, -1])

            # Risk score is 100% RF (GNN is used separately for hotspot prediction)
            risk_score = rf_score

            # Time-until-crime proxy from the Ridge regressor
            raw_window = self.trainer.regressor.predict(row)[0]
            predicted_window = int(np.clip(raw_window, 1, 100))

            # Store GNN hotspot probability on zone for patrol routing
            gnn_hotspot_prob = gnn_preds.get(zone.zone_id, 0.0)
            zone.gnn_hotspot_prob = gnn_hotspot_prob

            # is_hotspot considers both RF risk AND GNN spatial prediction
            rf_hotspot = risk_score > HOTSPOT_RISK_THRESHOLD
            gnn_hotspot = gnn_hotspot_prob > 0.5

            results[zone.zone_id] = {
                "risk_score": float(risk_score),
                "is_hotspot": bool(rf_hotspot or gnn_hotspot),
                "predicted_crime_window": predicted_window,
            }

        return results

    # ------------------------------------------------------------------ #
    #  Environment feedback                                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def update_environment(environment, predictions: dict) -> None:
        """Write prediction results back into the environment's zones.

        Parameters
        ----------
        environment : object
            Must expose ``get_zone(zone_id)`` returning a zone with
            ``risk_score`` and ``is_hotspot`` attributes.
        predictions : dict
            Output of :meth:`predict_all`.
        """
        for zone_id, prediction in predictions.items():
            zone = environment.get_zone(zone_id)
            if zone is None:
                continue
            zone.risk_score = prediction["risk_score"]
            zone.is_hotspot = prediction["is_hotspot"]
