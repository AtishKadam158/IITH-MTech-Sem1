from __future__ import annotations
from typing import Dict, Optional
import numpy as np


def _zeros(x: np.ndarray) -> np.ndarray:
    return np.zeros_like(x, dtype=float)


class Optimizer:
    def step(
        self,
        grads: Dict[str, np.ndarray],
        params: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        raise NotImplementedError


class SGD(Optimizer):
    def __init__(self, learning_rate: float = 0.01):
        self.lr = float(learning_rate)

    def step(self, grads, params):
        return {k: -self.lr * g for k, g in grads.items()}


class Momentum(Optimizer):
    def __init__(self, learning_rate: float = 0.01, beta: float = 0.9):
        self.lr   = float(learning_rate)
        self.beta = float(beta)
        self._v: Dict[str, np.ndarray] = {}

    def step(self, grads, params):
        out = {}
        for k, g in grads.items():
            if k not in self._v:
                self._v[k] = _zeros(g)
            self._v[k] = self.beta * self._v[k] + g
            out[k] = -self.lr * self._v[k]
        return out


class Nesterov(Optimizer):
    def __init__(self, learning_rate: float = 0.01, beta: float = 0.9):
        self.lr   = float(learning_rate)
        self.beta = float(beta)
        self._v: Dict[str, np.ndarray] = {}

    def step(self, grads, params):
        out = {}
        for k, g in grads.items():
            if k not in self._v:
                self._v[k] = _zeros(g)
            v_prev    = self._v[k].copy()
            self._v[k] = self.beta * self._v[k] - self.lr * g
            out[k]    = -self.beta * v_prev + (1.0 + self.beta) * self._v[k]
        return out


class AdaGrad(Optimizer):
    def __init__(self, learning_rate: float = 0.01, eps: float = 1e-8):
        self.lr  = float(learning_rate)
        self.eps = float(eps)
        self._cache: Dict[str, np.ndarray] = {}

    def step(self, grads, params):
        out = {}
        for k, g in grads.items():
            if k not in self._cache:
                self._cache[k] = _zeros(g)
            self._cache[k] += np.power(g, 2)
            out[k] = -self.lr * g / (np.sqrt(self._cache[k]) + self.eps)
        return out


class RMSProp(Optimizer):
    def __init__(self, learning_rate: float = 0.001, rho: float = 0.9, eps: float = 1e-8):
        self.lr  = float(learning_rate)
        self.rho = float(rho)
        self.eps = float(eps)
        self._cache: Dict[str, np.ndarray] = {}

    def step(self, grads, params):
        out = {}
        for k, g in grads.items():
            if k not in self._cache:
                self._cache[k] = _zeros(g)
            self._cache[k] = self.rho * self._cache[k] + (1.0 - self.rho) * np.power(g, 2)
            out[k] = -self.lr * g / (np.sqrt(self._cache[k]) + self.eps)
        return out


class Adam(Optimizer):
    def __init__(
        self,
        learning_rate: float = 0.001,
        beta1: float = 0.9,
        beta2: float = 0.999,
        eps: float = 1e-8,
    ):
        self.lr    = float(learning_rate)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.eps   = float(eps)
        self._m: Dict[str, np.ndarray] = {}
        self._v: Dict[str, np.ndarray] = {}
        self._t: int = 0

    def step(self, grads, params):
        self._t += 1
        out = {}
        for k, g in grads.items():
            if k not in self._m:
                self._m[k] = _zeros(g)
                self._v[k] = _zeros(g)
            self._m[k] = self.beta1 * self._m[k] + (1.0 - self.beta1) * g
            self._v[k] = self.beta2 * self._v[k] + (1.0 - self.beta2) * np.power(g, 2)
            m_hat = self._m[k] / (1.0 - np.power(self.beta1, self._t))
            v_hat = self._v[k] / (1.0 - np.power(self.beta2, self._t))
            out[k] = -self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
        return out


def _newton_schulz(G: np.ndarray, steps: int, eps: float) -> np.ndarray:
    a, b, c = 3.4445, -4.7750, 2.0315
    X = G.astype(float) / (np.linalg.norm(G) + eps)
    flipped = X.shape[0] > X.shape[1]
    if flipped:
        X = X.T
    for _ in range(steps):
        A = X @ X.T
        X = a * X + (b * A + c * (A @ A)) @ X
    return X.T if flipped else X


class Muon(Optimizer):
    def __init__(
        self,
        learning_rate: float = 0.01,
        momentum: float = 0.95,
        ns_steps: int = 5,
        eps: float = 1e-7,
        aux_optimizer: str = "adam",
        aux_lr: float = 0.001,
    ):
        self.lr       = float(learning_rate)
        self.mu       = float(momentum)
        self.ns_steps = int(ns_steps)
        self.eps      = float(eps)
        self._B: Dict[str, np.ndarray] = {}

        aux = aux_optimizer.lower()
        if aux == "adam":
            self._aux: Optimizer = Adam(learning_rate=float(aux_lr))
        elif aux == "sgd":
            self._aux = SGD(learning_rate=float(aux_lr))
        else:
            raise ValueError("aux_optimizer must be 'adam' or 'sgd'")

    def step(self, grads, params):
        g2d, gother = {}, {}
        for k, g in grads.items():
            (g2d if g.ndim == 2 else gother)[k] = g

        out = {}
        for k, g in g2d.items():
            if k not in self._B:
                self._B[k] = _zeros(g)
            self._B[k] = self.mu * self._B[k] + g
            out[k] = -self.lr * _newton_schulz(self._B[k], self.ns_steps, self.eps)

        if gother:
            out.update(self._aux.step(gother, params))
        return out


def make_optimizer(name: str, learning_rate: float, **kw) -> Optimizer:
    n = name.lower()
    lr = float(learning_rate)
    if n == "sgd":
        return SGD(lr)
    if n == "momentum":
        return Momentum(lr, beta=float(kw.get("beta", 0.9)))
    if n == "nesterov":
        return Nesterov(lr, beta=float(kw.get("beta", 0.9)))
    if n == "adagrad":
        return AdaGrad(lr, eps=float(kw.get("eps", 1e-8)))
    if n == "rmsprop":
        return RMSProp(lr, rho=float(kw.get("rho", 0.9)), eps=float(kw.get("eps", 1e-8)))
    if n == "adam":
        return Adam(lr,
                    beta1=float(kw.get("beta1", 0.9)),
                    beta2=float(kw.get("beta2", 0.999)),
                    eps=float(kw.get("eps", 1e-8)))
    if n == "muon":
        return Muon(lr,
                    momentum=float(kw.get("momentum", 0.95)),
                    ns_steps=int(kw.get("ns_steps", 5)),
                    eps=float(kw.get("eps", 1e-7)),
                    aux_optimizer=str(kw.get("aux_optimizer", "adam")),
                    aux_lr=float(kw.get("aux_lr", max(lr * 0.1, 1e-4))))
    raise ValueError(f"Unknown optimizer: {name!r}")