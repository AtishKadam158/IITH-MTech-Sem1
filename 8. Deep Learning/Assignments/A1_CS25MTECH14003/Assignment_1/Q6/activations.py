from __future__ import annotations
import numpy as np

STABILITY_CLIP = 60.0
EPSILON = 1e-12


def _safe_clip(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.minimum(np.maximum(arr, lo), hi)


def sigmoid(z: np.ndarray) -> np.ndarray:
    z = _safe_clip(z, -STABILITY_CLIP, STABILITY_CLIP)
    return 1.0 / (1.0 + np.exp(-z))


def sigmoid_grad(a: np.ndarray) -> np.ndarray:
    return a * (1.0 - a)


def tanh_act(z: np.ndarray) -> np.ndarray:
    z = _safe_clip(z, -STABILITY_CLIP, STABILITY_CLIP)
    pos = np.exp(z)
    neg = np.exp(-z)
    return (pos - neg) / (pos + neg)


def tanh_grad(a: np.ndarray) -> np.ndarray:
    return 1.0 - np.power(a, 2)


def relu(z: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, z)


def relu_grad(z: np.ndarray) -> np.ndarray:
    return (z > 0.0).astype(z.dtype)


def leaky_relu(z: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    return np.where(z > 0.0, z, alpha * z)


def leaky_relu_grad(z: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    return np.where(z > 0.0, 1.0, alpha).astype(z.dtype)


def linear_act(z: np.ndarray) -> np.ndarray:
    return z.copy()


def linear_grad(z: np.ndarray) -> np.ndarray:
    return np.ones_like(z)


def softmax(z: np.ndarray, axis: int = 1) -> np.ndarray:
    shifted = z - np.max(z, axis=axis, keepdims=True)
    exps = np.exp(shifted)
    return exps / (np.sum(exps, axis=axis, keepdims=True) + EPSILON)


_FORWARD_MAP = {
    "sigmoid":    lambda z, kw: sigmoid(z),
    "tanh":       lambda z, kw: tanh_act(z),
    "relu":       lambda z, kw: relu(z),
    "leaky_relu": lambda z, kw: leaky_relu(z, kw.get("alpha", 0.01)),
    "lrelu":      lambda z, kw: leaky_relu(z, kw.get("alpha", 0.01)),
    "linear":     lambda z, kw: linear_act(z),
    "identity":   lambda z, kw: linear_act(z),
    "softmax":    lambda z, kw: softmax(z, axis=1),
}

_GRAD_MAP = {
    "sigmoid":    lambda z, a, kw: sigmoid_grad(a),
    "tanh":       lambda z, a, kw: tanh_grad(a),
    "relu":       lambda z, a, kw: relu_grad(z),
    "leaky_relu": lambda z, a, kw: leaky_relu_grad(z, kw.get("alpha", 0.01)),
    "lrelu":      lambda z, a, kw: leaky_relu_grad(z, kw.get("alpha", 0.01)),
    "linear":     lambda z, a, kw: linear_grad(z),
    "identity":   lambda z, a, kw: linear_grad(z),
}


def activate(name: str, z: np.ndarray, **kwargs) -> np.ndarray:
    key = name.lower().replace("-", "_")
    if key not in _FORWARD_MAP:
        raise ValueError(f"Unknown activation: {name!r}")
    return _FORWARD_MAP[key](z, kwargs)


def grad(name: str, z: np.ndarray, a: np.ndarray, **kwargs) -> np.ndarray:
    key = name.lower().replace("-", "_")
    if key == "softmax":
        raise NotImplementedError("Use combined softmax+cross-entropy gradient instead.")
    if key not in _GRAD_MAP:
        raise ValueError(f"Unknown activation: {name!r}")
    return _GRAD_MAP[key](z, a, kwargs)