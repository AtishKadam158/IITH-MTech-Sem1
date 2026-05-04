from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import activations as act
import losses
from optimizers import Optimizer, make_optimizer


@dataclass
class _Cfg:
    layer_sizes:    List[int]
    activations:    List[str]
    loss:           str            = "cross_entropy"
    learning_rate:  float          = 0.01
    optimizer:      str            = "sgd"
    batch_size:     int            = 32
    weight_init:    str            = "xavier"
    regularization: Optional[str] = None
    lambda_reg:     float          = 0.01
    seed:           int            = 0
    leaky_alpha:    float          = 0.01
    patience:       int            = 20
    min_delta:      float          = 1e-4


def _to_onehot(y: np.ndarray, n_cls: int) -> np.ndarray:
    flat = y.astype(int).reshape(-1)
    mat = np.zeros((flat.shape[0], n_cls), dtype=float)
    mat[np.arange(flat.shape[0]), flat] = 1.0
    return mat


class MLP:
    def __init__(
        self,
        layer_sizes: List[int],
        activations: List[str],
        loss: str = "cross_entropy",
        learning_rate: float = 0.01,
        optimizer: str = "sgd",
        batch_size: int = 32,
        weight_init: str = "xavier",
        regularization: Optional[str] = None,
        lambda_reg: float = 0.01,
        seed: int = 0,
        leaky_alpha: float = 0.01,
        optimizer_kwargs: Optional[Dict[str, Any]] = None,
        patience: int = 20,
        min_delta: float = 1e-4,
    ):
        self.cfg = _Cfg(
            layer_sizes=list(layer_sizes),
            activations=list(activations),
            loss=loss.lower(),
            learning_rate=float(learning_rate),
            optimizer=optimizer.lower(),
            batch_size=int(batch_size),
            weight_init=weight_init.lower(),
            regularization=None if regularization is None else regularization.lower(),
            lambda_reg=float(lambda_reg),
            seed=int(seed),
            leaky_alpha=float(leaky_alpha),
            patience=int(patience),
            min_delta=float(min_delta),
        )

        if len(self.cfg.layer_sizes) < 2:
            raise ValueError("layer_sizes needs at least [input_dim, output_dim]")
        if len(self.cfg.activations) != len(self.cfg.layer_sizes) - 1:
            raise ValueError("len(activations) must equal len(layer_sizes) - 1")

        self._rng = np.random.default_rng(self.cfg.seed)
        self.params: Dict[str, np.ndarray] = {}
        self._build_params()

        self._opt: Optimizer = make_optimizer(
            self.cfg.optimizer,
            self.cfg.learning_rate,
            **(optimizer_kwargs or {}),
        )
        self.history_: Dict[str, list] = {}

    
    # Parameter initialisation
    
    def _make_weight(self, fan_in: int, fan_out: int) -> np.ndarray:
        scheme = self.cfg.weight_init
        if scheme == "random":
            return self._rng.normal(0.0, 0.01, (fan_in, fan_out))
        if scheme == "xavier":
            bound = np.sqrt(6.0 / (fan_in + fan_out))
            return self._rng.uniform(-bound, bound, (fan_in, fan_out))
        if scheme == "he":
            return self._rng.normal(0.0, np.sqrt(2.0 / fan_in), (fan_in, fan_out))
        raise ValueError("weight_init must be 'random', 'xavier', or 'he'")

    def _build_params(self) -> None:
        for idx in range(1, len(self.cfg.layer_sizes)):
            fi = self.cfg.layer_sizes[idx - 1]
            fo = self.cfg.layer_sizes[idx]
            self.params[f"W{idx}"] = self._make_weight(fi, fo).astype(float)
            self.params[f"b{idx}"] = np.zeros(fo, dtype=float)

    def _copy_params(self) -> Dict[str, np.ndarray]:
        return {k: v.copy() for k, v in self.params.items()}

    def _load_params(self, src: Dict[str, np.ndarray]) -> None:
        for k in self.params:
            self.params[k] = src[k].copy()

    
    # Forward / backward
    
    def forward(self, X: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        A, Z = [np.asarray(X, dtype=float)], []
        for idx in range(1, len(self.cfg.layer_sizes)):
            W, b = self.params[f"W{idx}"], self.params[f"b{idx}"]
            z = A[-1] @ W + b
            Z.append(z)
            A.append(act.activate(self.cfg.activations[idx - 1], z, alpha=self.cfg.leaky_alpha))
        return A, Z

    def _reg_loss(self, n: int) -> float:
        if self.cfg.regularization is None:
            return 0.0
        scale = self.cfg.lambda_reg / float(max(1, n))
        total = 0.0
        for idx in range(1, len(self.cfg.layer_sizes)):
            W = self.params[f"W{idx}"]
            if self.cfg.regularization == "l2":
                total += 0.5 * float(np.sum(np.power(W, 2)))
            elif self.cfg.regularization == "l1":
                total += float(np.sum(np.abs(W)))
            else:
                raise ValueError("regularization must be None, 'l1', or 'l2'")
        return scale * total

    def _reg_grads(self, grads: Dict[str, np.ndarray], n: int) -> None:
        if self.cfg.regularization is None:
            return
        scale = self.cfg.lambda_reg / float(max(1, n))
        for idx in range(1, len(self.cfg.layer_sizes)):
            key = f"W{idx}"
            W = self.params[key]
            if self.cfg.regularization == "l2":
                grads[key] = grads[key] + scale * W
            elif self.cfg.regularization == "l1":
                grads[key] = grads[key] + scale * np.sign(W)

    def _output_grad(self, y: np.ndarray, A_out: np.ndarray, Z_out: np.ndarray) -> np.ndarray:
        loss = self.cfg.loss

        if loss == "mse":
            dA = losses.d_mse(y.reshape(A_out.shape).astype(float), A_out)
            return dA * act.grad(self.cfg.activations[-1], Z_out, A_out, alpha=self.cfg.leaky_alpha)

        if loss == "cross_entropy":
            if A_out.shape[1] == 1:
                return losses.d_bce_logits(y.reshape(-1, 1).astype(float), A_out)
            y_oh = y.astype(float) if (y.ndim == 2 and y.shape[1] > 1) else _to_onehot(y, A_out.shape[1])
            return losses.d_softmax_ce_logits(y_oh, A_out)

        if loss == "hinge":
            return losses.d_hinge(y.reshape(-1, 1).astype(float), A_out)

        raise ValueError("loss must be 'mse', 'cross_entropy', or 'hinge'")

    def backward(self, X: np.ndarray, y: np.ndarray) -> Dict[str, np.ndarray]:
        A, Z = self.forward(np.asarray(X, dtype=float))
        n = A[-1].shape[0]
        L = len(self.cfg.layer_sizes) - 1
        grads: Dict[str, np.ndarray] = {}

        dZ = self._output_grad(y, A[-1], Z[-1])

        for l in range(L, 0, -1):
            grads[f"W{l}"] = A[l - 1].T @ dZ
            grads[f"b{l}"] = np.sum(dZ, axis=0)
            if l > 1:
                dA_prev = dZ @ self.params[f"W{l}"].T
                dZ = dA_prev * act.grad(
                    self.cfg.activations[l - 2], Z[l - 2], A[l - 1], alpha=self.cfg.leaky_alpha
                )

        self._reg_grads(grads, n)
        return grads

    # Loss + accuracy

    def _batch_metrics(self, X: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        A, _ = self.forward(X)
        out = A[-1]
        n = out.shape[0]
        loss = self.cfg.loss

        if loss == "mse":
            y_t = y.reshape(out.shape).astype(float)
            base = losses.mse(y_t, out)
            acc = float(np.mean(np.abs(out - y_t) < 0.1))

        elif loss == "cross_entropy":
            if out.shape[1] == 1:
                y_t = y.reshape(-1, 1).astype(float)
                base = losses.binary_cross_entropy(y_t, out)
                acc = float(np.mean((out >= 0.5).astype(float) == y_t))
            else:
                y_oh = y.astype(float) if (y.ndim == 2 and y.shape[1] > 1) else _to_onehot(y, out.shape[1])
                y_int = np.argmax(y_oh, axis=1)
                base = losses.softmax_cross_entropy(y_oh, out)
                acc = float(np.mean(np.argmax(out, axis=1) == y_int))

        elif loss == "hinge":
            y_t = y.reshape(-1, 1).astype(float)
            base = losses.hinge(y_t, out)
            acc = float(np.mean(np.where(out >= 0.0, 1.0, -1.0) == y_t))

        else:
            raise ValueError("loss must be 'mse', 'cross_entropy', or 'hinge'")

        return float(base + self._reg_loss(n)), float(acc)

    # Training
    def _minibatches(self, X: np.ndarray, y: np.ndarray):
        n = X.shape[0]
        idx = np.arange(n)
        self._rng.shuffle(idx)
        bs = max(1, self.cfg.batch_size)
        for s in range(0, n, bs):
            sl = idx[s:s + bs]
            yield X[sl], y[sl]

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 100,
        verbose: bool = True,
        track_grads: bool = True,
        track_dead: bool = True,
    ) -> Dict[str, list]:
        import time

        Xtr = np.asarray(X_train, dtype=float)
        Xv  = np.asarray(X_val,   dtype=float)
        ytr = np.asarray(y_train)
        yv  = np.asarray(y_val)

        L = len(self.cfg.layer_sizes) - 1
        hist: Dict[str, list] = {
            "train_loss": [], "val_loss": [],
            "train_acc":  [], "val_acc":  [],
            "epoch_time_sec": [],
            "grad_mean": [], "grad_std": [], "grad_abs_mean": [],
            "dead_frac": [], "update_norm": [],
        }

        best_params   = self._copy_params()
        best_val_loss = float("inf")
        patience_left = self.cfg.patience
        probe_n       = min(256, Xtr.shape[0])
        probe_idx     = np.arange(probe_n)

        for epoch in range(1, int(epochs) + 1):
            t0 = time.perf_counter()
            norm_acc   = [0.0] * L
            norm_count = 0

            for Xb, yb in self._minibatches(Xtr, ytr):
                grads  = self.backward(Xb, yb)
                deltas = self._opt.step(grads, self.params)
                for l in range(1, L + 1):
                    self.params[f"W{l}"] += deltas[f"W{l}"]
                    self.params[f"b{l}"] += deltas[f"b{l}"]
                    norm_acc[l - 1] += float(np.linalg.norm(deltas[f"W{l}"]))
                norm_count += 1

            tr_loss, tr_acc = self._batch_metrics(Xtr, ytr)
            vl_loss, vl_acc = self._batch_metrics(Xv,  yv)

            hist["train_loss"].append(tr_loss)
            hist["val_loss"].append(vl_loss)
            hist["train_acc"].append(tr_acc)
            hist["val_acc"].append(vl_acc)
            hist["update_norm"].append([v / max(1, norm_count) for v in norm_acc])
            hist["epoch_time_sec"].append(time.perf_counter() - t0)

            if track_grads:
                g = self.backward(Xtr[probe_idx], ytr[probe_idx])
                hist["grad_mean"].append([float(np.mean(g[f"W{l}"])) for l in range(1, L + 1)])
                hist["grad_std"].append([float(np.std(g[f"W{l}"])) for l in range(1, L + 1)])
                hist["grad_abs_mean"].append([float(np.mean(np.abs(g[f"W{l}"]))) for l in range(1, L + 1)])
            else:
                hist["grad_mean"].append([])
                hist["grad_std"].append([])
                hist["grad_abs_mean"].append([])

            if track_dead:
                Ap, _ = self.forward(Xtr[probe_idx])
                dead_row = []
                for l in range(1, L):
                    name = self.cfg.activations[l - 1].lower()
                    if name in ("relu", "leaky_relu", "leaky-relu", "lrelu"):
                        dead_row.append(float(np.mean(Ap[l] <= 0.0)))
                    else:
                        dead_row.append(float("nan"))
                hist["dead_frac"].append(dead_row)
            else:
                hist["dead_frac"].append([])

            if verbose and (epoch == 1 or epoch % max(1, epochs // 10) == 0 or epoch == epochs):
                print(
                    f"[{epoch:>4}/{epochs}] "
                    f"train loss={tr_loss:.5f} acc={tr_acc:.4f}  "
                    f"val loss={vl_loss:.5f} acc={vl_acc:.4f}"
                )

            if vl_loss < best_val_loss - self.cfg.min_delta:
                best_val_loss = vl_loss
                best_params   = self._copy_params()
                patience_left = self.cfg.patience
            else:
                patience_left -= 1
                if patience_left <= 0:
                    if verbose:
                        print(f"Early stop at epoch {epoch}  best_val_loss={best_val_loss:.6f}")
                    break

        self._load_params(best_params)
        self.history_ = hist
        return hist

    # Inference
    def predict(self, X: np.ndarray) -> np.ndarray:
        A, _ = self.forward(X)
        out  = A[-1]
        if self.cfg.loss == "hinge":
            return np.where(out >= 0.0, 1.0, -1.0)
        if self.cfg.loss == "cross_entropy":
            if out.shape[1] == 1:
                return (out >= 0.5).astype(int)
            return np.argmax(out, axis=1).astype(int)
        return out

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        A, _ = self.forward(X)
        return A[-1]

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        loss, acc = self._batch_metrics(np.asarray(X, dtype=float), np.asarray(y))
        return {"loss": loss, "acc": acc}