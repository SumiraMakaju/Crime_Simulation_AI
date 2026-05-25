"""dataset.py — Feature extraction and dataset loading for crime prediction ML."""

import pandas as pd

from config import DATASET_CSV


# ─── Ordered feature column names ──────────────────────────────────────────────
_ZONE_TYPE_DUMMIES = [
    "zone_type_residential",
    "zone_type_commercial",
    "zone_type_park",
    "zone_type_intersection",
]

_FEATURE_COLUMNS = [
    "time_of_day",
    "zone_type_residential",
    "zone_type_commercial",
    "zone_type_park",
    "zone_type_intersection",
    "lighting",
    "population",
    "police_count",
    "historical_crimes_count",
    "neighbor_avg_risk",
    "neighbor_police_sum",
]


class FeatureExtractor:
    """Converts a zone + environment snapshot into a flat feature dictionary."""

    # ------------------------------------------------------------------ #
    #  Public helpers                                                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def feature_columns() -> list[str]:
        """Return the ordered list of feature names used by the model."""
        return list(_FEATURE_COLUMNS)

    # ------------------------------------------------------------------ #
    #  Core extraction                                                     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def extract(zone, environment) -> dict:
        """Build a feature dictionary from a *zone* object and an
        *environment* context object.

        Parameters
        ----------
        zone : object
            Must expose: `zone_type` (str), `lighting` (float),
            `population` (int), `police_count` (int),
            `historical_crimes` (list), and `zone_id`.
        environment : object
            Must expose: `time_of_day` (float),
            `get_neighbor_avg_risk(zone_id)` (float),
            `get_neighbor_police_sum(zone_id)` (int).

        Returns
        -------
        dict
            Feature name → value, in the canonical order defined by
            ``feature_columns()``.
        """
        zone_type = getattr(zone, "zone_type", "residential").lower()

        return {
            "time_of_day": float(environment.time_of_day),
            "zone_type_residential": 1 if zone_type == "residential" else 0,
            "zone_type_commercial": 1 if zone_type == "commercial" else 0,
            "zone_type_park": 1 if zone_type == "park" else 0,
            "zone_type_intersection": 1 if zone_type == "intersection" else 0,
            "lighting": float(zone.lighting),
            "population": int(zone.population),
            "police_count": int(zone.police_count),
            "historical_crimes_count": int(len(zone.historical_crimes)),
            "neighbor_avg_risk": float(
                environment.get_neighbor_avg_risk(zone.zone_id)
            ),
            "neighbor_police_sum": int(
                environment.get_neighbor_police_sum(zone.zone_id)
            ),
        }


# ─── Dataset loader ────────────────────────────────────────────────────────────

def load_dataset(path: str = DATASET_CSV) -> tuple[pd.DataFrame, pd.Series]:
    """Load the crime dataset CSV and return *(X, y)*.

    The CSV is expected to contain a string ``zone_type`` column which is
    one-hot encoded into the four canonical dummy columns.  Any missing
    values are filled with ``0``.

    Parameters
    ----------
    path : str
        File-system path to the CSV (defaults to ``DATASET_CSV`` from
        ``config``).

    Returns
    -------
    tuple[pd.DataFrame, pd.Series]
        ``X`` — feature DataFrame with columns in canonical order.
        ``y`` — binary label Series (``crime_occurred``).
    """
    df = pd.read_csv(path)

    # ── One-hot encode zone_type ──────────────────────────────────────
    if "zone_type" in df.columns:
        dummies = pd.get_dummies(df["zone_type"], prefix="zone_type")
        df = pd.concat([df.drop(columns=["zone_type"]), dummies], axis=1)

    # Ensure all four zone-type dummy columns exist
    for col in _ZONE_TYPE_DUMMIES:
        if col not in df.columns:
            df[col] = 0

    # ── Fill missing values ───────────────────────────────────────────
    df = df.fillna(0)

    # ── Build X, y ────────────────────────────────────────────────────
    y = df["crime_occurred"].astype(int)
    X = df[_FEATURE_COLUMNS].copy()

    return X, y
