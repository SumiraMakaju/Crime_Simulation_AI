"""train_model.py — Model training, evaluation, and online retraining."""

import os

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from config import (
    ML_MIN_ROWS,
    ML_N_ESTIMATORS,
    ML_RETRAIN_INTERVAL,
    MODEL_PATH,
    RIDGE_MODEL_PATH,
)


class ModelTrainer:
    """Trains, evaluates, saves, and loads crime-prediction models.

    Two models are maintained:
    * **classifier** — ``RandomForestClassifier`` for binary
      crime-occurred prediction.
    * **regressor** — ``Ridge`` regression used as a continuous proxy for
      the *time-until-crime* window.
    """

    def __init__(self) -> None:
        self.classifier = RandomForestClassifier(
            n_estimators=ML_N_ESTIMATORS,
            random_state=42,
        )
        self.regressor = Ridge(alpha=1.0)
        self.is_trained: bool = False
        self.last_train_size: int = 0
        self.eval_metrics: dict = {}
        self.X_test = None
        self.y_test = None

    # ------------------------------------------------------------------ #
    #  Training                                                            #
    # ------------------------------------------------------------------ #
    def train(self, X, y) -> dict:
        """Train both models on *(X, y)* with an 80/20 train-test split.

        Parameters
        ----------
        X : pd.DataFrame | np.ndarray
            Feature matrix.
        y : pd.Series | np.ndarray
            Binary labels.

        Returns
        -------
        dict
            Evaluation metrics computed on the held-out test split.
        """
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42,
        )

        self.classifier.fit(X_train, y_train)
        self.regressor.fit(X_train, y_train)  # treat label as continuous proxy

        self.eval_metrics = self.evaluate(X_test, y_test)
        self.is_trained = True
        self.last_train_size = len(X)
        self.X_test = X_test
        self.y_test = y_test
        return self.eval_metrics

    def get_feature_importances(self) -> tuple[list[str], list[float]]:
        """Returns feature names and their relative importances."""
        if not self.is_trained:
            return [], []
        importances = self.classifier.feature_importances_
        from ml.dataset import FeatureExtractor
        names = FeatureExtractor.feature_columns()
        return names, list(importances)

    # ------------------------------------------------------------------ #
    #  Evaluation                                                          #
    # ------------------------------------------------------------------ #
    def evaluate(self, X_test, y_test) -> dict:
        """Compute and store classification metrics.

        Parameters
        ----------
        X_test : pd.DataFrame | np.ndarray
            Test features.
        y_test : pd.Series | np.ndarray
            True labels.

        Returns
        -------
        dict
            Keys: ``precision``, ``recall``, ``f1``, ``roc_auc``.
        """
        y_pred = self.classifier.predict(X_test)

        # classification_report as dict keyed by label string
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        weighted = report.get("weighted avg", {})

        # ROC-AUC requires both classes to be present in y_test
        try:
            y_proba = self.classifier.predict_proba(X_test)[:, 1]
            roc_auc = float(roc_auc_score(y_test, y_proba))
        except (ValueError, IndexError):
            roc_auc = 0.0

        self.eval_metrics = {
            "precision": float(weighted.get("precision", 0.0)),
            "recall": float(weighted.get("recall", 0.0)),
            "f1": float(weighted.get("f1-score", 0.0)),
            "roc_auc": roc_auc,
        }
        return self.eval_metrics

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #
    def save(self, path: str | None = None) -> None:
        """Serialize both models to disk.

        Parameters
        ----------
        path : str | None
            If given, used as the classifier path (regressor path is
            derived automatically).  Defaults to ``MODEL_PATH`` /
            ``RIDGE_MODEL_PATH`` from config.
        """
        clf_path = path or MODEL_PATH
        reg_path = RIDGE_MODEL_PATH

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(clf_path) or ".", exist_ok=True)

        joblib.dump(self.classifier, clf_path)
        joblib.dump(self.regressor, reg_path)
        print(f"[ModelTrainer] Classifier saved -> {clf_path}")
        print(f"[ModelTrainer] Regressor  saved -> {reg_path}")

    def load(self, path: str | None = None) -> bool:
        """Load previously-saved models from disk.

        Parameters
        ----------
        path : str | None
            Classifier path override.

        Returns
        -------
        bool
            ``True`` if both models were loaded successfully.
        """
        clf_path = path or MODEL_PATH
        reg_path = RIDGE_MODEL_PATH

        if os.path.isfile(clf_path) and os.path.isfile(reg_path):
            self.classifier = joblib.load(clf_path)
            self.regressor = joblib.load(reg_path)
            self.is_trained = True
            print(f"[ModelTrainer] Models loaded from {clf_path}, {reg_path}")
            return True

        print("[ModelTrainer] Model files not found — skipping load.")
        return False

    # ------------------------------------------------------------------ #
    #  Online / incremental retraining                                     #
    # ------------------------------------------------------------------ #
    def online_retrain(self, X, y) -> dict:
        """Retrain on the full accumulated dataset.

        Functionally identical to :meth:`train` but intended to be called
        incrementally as new crime events are collected.

        Returns
        -------
        dict
            Updated evaluation metrics.
        """
        metrics = self.train(X, y)
        return metrics

    def should_retrain(self, current_size: int) -> bool:
        """Decide whether enough new data has arrived to justify retraining.

        Parameters
        ----------
        current_size : int
            Current number of rows in the dataset.

        Returns
        -------
        bool
            ``True`` when the number of new rows since the last training
            equals or exceeds ``ML_RETRAIN_INTERVAL``.
        """
        return current_size - self.last_train_size >= ML_RETRAIN_INTERVAL
