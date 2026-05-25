"""predict.py — Crime risk prediction using trained ML models."""

import numpy as np
import pandas as pd

from config import HOTSPOT_RISK_THRESHOLD, MODEL_PATH
from ml.dataset import FeatureExtractor
from ml.train_model import ModelTrainer


class CrimePredictor:
    """High-level facade that wires together :class:`ModelTrainer` and
    :class:`FeatureExtractor` to produce per-zone crime risk predictions.
    """

    def __init__(self) -> None:
        self.trainer: ModelTrainer | None = None
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

        for zone in environment.zones.values():
            features = self.extractor.extract(zone, environment)

            # Build a single-row DataFrame in canonical column order
            row = pd.DataFrame([features], columns=columns)

            # Probability of crime (class = 1)
            proba = self.trainer.classifier.predict_proba(row)
            # predict_proba returns shape (1, n_classes); class-1 is last col
            risk_score = float(proba[0, -1])

            # Time-until-crime proxy from the Ridge regressor
            raw_window = self.trainer.regressor.predict(row)[0]
            predicted_window = int(np.clip(raw_window, 1, 100))

            results[zone.zone_id] = {
                "risk_score": float(risk_score),
                "is_hotspot": bool(risk_score > HOTSPOT_RISK_THRESHOLD),
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
