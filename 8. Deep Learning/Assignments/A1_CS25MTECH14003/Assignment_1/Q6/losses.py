from __future__ import annotations
import numpy as np

_CLIP_LOW = 1e-12


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(0.5 * np.mean(np.power(y_pred - y_true, 2)))


def d_mse(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return (y_pred - y_true) / float(y_true.shape[0])


def binary_cross_entropy(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    p = np.clip(y_prob, _CLIP_LOW, 1.0 - _CLIP_LOW)
    return float(-np.mean(y_true * np.log(p) + (1.0 - y_true) * np.log(1.0 - p)))


def d_bce_logits(y_true: np.ndarray, y_prob: np.ndarray) -> np.ndarray:
    return (y_prob - y_true) / float(y_true.shape[0])


def softmax_cross_entropy(y_onehot: np.ndarray, y_prob: np.ndarray) -> float:
    p = np.clip(y_prob, _CLIP_LOW, 1.0 - _CLIP_LOW)
    return float(-np.mean(np.sum(y_onehot * np.log(p), axis=1)))


def d_softmax_ce_logits(y_onehot: np.ndarray, y_prob: np.ndarray) -> np.ndarray:
    return (y_prob - y_onehot) / float(y_onehot.shape[0])


def hinge(y_true: np.ndarray, scores: np.ndarray) -> float:
    return float(np.mean(np.maximum(0.0, 1.0 - y_true * scores)))


def d_hinge(y_true: np.ndarray, scores: np.ndarray) -> np.ndarray:
    mask = (1.0 - y_true * scores > 0.0).astype(float)
    return (-y_true * mask) / float(y_true.shape[0])