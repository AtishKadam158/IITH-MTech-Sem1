from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_REQUIRED_COLS = [
    "student_id", "day_of_week", "meal_time", "meal_type",
    "is_weekend", "class_day", "assignment_deadline",
    "temperature_c", "humidity", "wind_speed", "rain_mm",
    "air_quality_index", "rising_time_min", "sleeping_time_min",
    "mess_duration_min",
]

_INT_COLS = [
    "student_id", "day_of_week", "meal_time", "meal_type",
    "is_weekend", "class_day", "assignment_deadline",
    "rising_time_min", "sleeping_time_min",
]

_CATEGORICAL = {
    "day_of_week": 7,
    "meal_time":   3,
}

_BINARY_AND_NUMERIC = [
    "meal_type", "is_weekend", "class_day", "assignment_deadline",
    "temperature_c", "humidity", "wind_speed", "rain_mm",
    "air_quality_index", "rising_time_min", "sleeping_time_min",
]


def _load_raw(path: Path) -> Dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in _REQUIRED_COLS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        rows = list(reader)

    bucket: Dict[str, List[float]] = {c: [] for c in _REQUIRED_COLS}
    for row in rows:
        for col in _REQUIRED_COLS:
            bucket[col].append(float(row[col]))

    arrays = {c: np.asarray(v) for c, v in bucket.items()}
    for col in _INT_COLS:
        arrays[col] = arrays[col].astype(int)
    return arrays


def _encode_onehot(values: np.ndarray, n_classes: int) -> np.ndarray:
    vals = values.astype(int).reshape(-1)
    # shift to zero-based if minimum is 1
    if vals.min() > 0:
        vals = vals - vals.min()
    mat = np.zeros((vals.shape[0], n_classes), dtype=float)
    mat[np.arange(vals.shape[0]), vals] = 1.0
    return mat


def _assemble_features(
    arrays: Dict[str, np.ndarray],
    include_student_id: bool = False,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    n = arrays["mess_duration_min"].shape[0]
    blocks, names = [], []

    if include_student_id:
        blocks.append(arrays["student_id"].reshape(n, 1).astype(float))
        names.append("student_id")

    for col, n_cls in _CATEGORICAL.items():
        blocks.append(_encode_onehot(arrays[col], n_cls))
        names.extend([f"{col}_{i}" for i in range(n_cls)])

    for col in _BINARY_AND_NUMERIC:
        blocks.append(arrays[col].reshape(n, 1).astype(float))
        names.append(col)

    X = np.concatenate(blocks, axis=1)
    y = arrays["mess_duration_min"].astype(float)
    return X, y, names


def split_indices(
    n: int,
    test_ratio: float = 0.2,
    val_ratio: float = 0.2,
    seed: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    idx = np.arange(n)
    rng.shuffle(idx)
    n_test = int(np.round(test_ratio * n))
    rest = idx[n_test:]
    n_val = int(np.round(val_ratio * rest.shape[0]))
    return rest[n_val:], rest[:n_val], idx[:n_test]


def fit_scaler(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mu = np.mean(X, axis=0)
    sigma = np.std(X, axis=0)
    sigma = np.where(sigma < 1e-12, 1.0, sigma)
    return mu, sigma


def apply_scaler(X: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    return (X - mu) / sigma


def fit_pca(X: np.ndarray, n_components: int = 2) -> np.ndarray:
    cov = (X.T @ X) / float(X.shape[0] - 1)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    return vecs[:, order][:, :n_components]


def apply_pca(X: np.ndarray, components: np.ndarray) -> np.ndarray:
    return X @ components


@dataclass
class Dataset:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    threshold: float
    feature_names: List[str]
    scaler_mean: np.ndarray
    scaler_std: np.ndarray
    X_pca: np.ndarray
    pca_axes: np.ndarray
    y_raw: np.ndarray
    y_binary: np.ndarray


def prepare(
    csv_path: Path,
    seed: int = 0,
    threshold: Optional[float] = None,
    include_student_id: bool = False,
) -> Dataset:
    arrays = _load_raw(csv_path)
    X_raw, y_dur, feat_names = _assemble_features(arrays, include_student_id)

    tr_idx, val_idx, te_idx = split_indices(X_raw.shape[0], seed=seed)
    trainval = np.concatenate([tr_idx, val_idx])

    cutoff = float(np.median(y_dur[trainval])) if threshold is None else float(threshold)
    y_bin = (y_dur >= cutoff).astype(float).reshape(-1, 1)

    mu, sigma = fit_scaler(X_raw[tr_idx])
    X = apply_scaler(X_raw, mu, sigma)

    axes = fit_pca(X[tr_idx], n_components=2)
    X_pca = apply_pca(X, axes)

    return Dataset(
        X_train=X[tr_idx],      y_train=y_bin[tr_idx],
        X_val=X[val_idx],       y_val=y_bin[val_idx],
        X_test=X[te_idx],       y_test=y_bin[te_idx],
        threshold=cutoff,
        feature_names=feat_names,
        scaler_mean=mu,         scaler_std=sigma,
        X_pca=X_pca,            pca_axes=axes,
        y_raw=y_dur,            y_binary=y_bin.reshape(-1),
    )