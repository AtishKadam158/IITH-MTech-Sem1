from __future__ import annotations
import os, time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data_utils import prepare, fit_pca, apply_pca, Dataset
from mlp import MLP

OUT = Path("outputs_task6")
OUT.mkdir(exist_ok=True)

CSV = Path("iith_campus_life_5000.csv")
EPOCHS   = 150
PATIENCE = 20
BATCH    = 64
SEED     = 0

# ── helpers ────────────────────────────────────────────────────────────────

def _savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  → {OUT/name}")


def _build(d: Dataset, layer_sizes, activations, loss="cross_entropy",
           lr=0.01, optimizer="adam", reg=None, lam=0.01, seed=SEED) -> MLP:
    return MLP(
        layer_sizes=layer_sizes,
        activations=activations,
        loss=loss,
        learning_rate=lr,
        optimizer=optimizer,
        batch_size=BATCH,
        weight_init="xavier",
        regularization=reg,
        lambda_reg=lam,
        patience=PATIENCE,
        seed=seed,
    )


def _train(model: MLP, d: Dataset, epochs=EPOCHS,
           verbose=False, track_grads=True, track_dead=True):
    return model.fit(d.X_train, d.y_train, d.X_val, d.y_val,
                     epochs=epochs, verbose=verbose,
                     track_grads=track_grads, track_dead=track_dead)


def _acc(model: MLP, d: Dataset) -> float:
    return model.evaluate(d.X_test, d.y_test)["acc"]


def _count_params(layer_sizes: List[int]) -> int:
    total = 0
    for i in range(1, len(layer_sizes)):
        total += layer_sizes[i - 1] * layer_sizes[i] + layer_sizes[i]
    return total


def _hinge_labels(y: np.ndarray) -> np.ndarray:
    return np.where(y >= 0.5, 1.0, -1.0)


# ── 6.3.1  Depth ablation ──────────────────────────────────────────────────

def sec_631(d: Dataset, n_in: int) -> None:
    print("\n[6.3.1] Depth ablation")
    depths = [1, 2, 3, 4]
    configs = {
        k: [n_in] + [64] * k + [1] for k in depths
    }
    acts = {
        k: ["relu"] * k + ["sigmoid"] for k in depths
    }
    results: Dict[int, dict] = {}

    fig_lc, axes_lc = plt.subplots(4, 2, figsize=(12, 16))

    for row, k in enumerate(depths):
        m = _build(d, configs[k], acts[k])
        t0 = time.perf_counter()
        h = _train(m, d, track_grads=False, track_dead=False)
        elapsed = time.perf_counter() - t0
        test_acc = _acc(m, d)
        mean_epoch_t = float(np.mean(h["epoch_time_sec"]))
        train_val_gap = h["train_acc"][-1] - h["val_acc"][-1]
        results[k] = dict(test_acc=test_acc, mean_epoch_t=mean_epoch_t,
                          gap=train_val_gap, hist=h)
        print(f"  depth={k}  test_acc={test_acc:.4f}  epoch_time={mean_epoch_t*1000:.1f}ms  "
              f"train-val gap={train_val_gap:.4f}")

        ep = range(1, len(h["train_loss"]) + 1)
        axes_lc[row, 0].plot(ep, h["train_loss"], label="train")
        axes_lc[row, 0].plot(ep, h["val_loss"],   label="val")
        axes_lc[row, 0].set_title(f"Depth {k} – Loss")
        axes_lc[row, 0].set_xlabel("Epoch"); axes_lc[row, 0].set_ylabel("Loss")
        axes_lc[row, 0].legend()

        axes_lc[row, 1].plot(ep, h["train_acc"], label="train")
        axes_lc[row, 1].plot(ep, h["val_acc"],   label="val")
        axes_lc[row, 1].set_title(f"Depth {k} – Accuracy")
        axes_lc[row, 1].set_xlabel("Epoch"); axes_lc[row, 1].set_ylabel("Accuracy")
        axes_lc[row, 1].legend()

    _savefig("631_depth_curves.png")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].bar(depths, [results[k]["test_acc"]    for k in depths], color="steelblue")
    axes[0].set_xlabel("Depth"); axes[0].set_ylabel("Test Accuracy")
    axes[0].set_title("Test Accuracy vs Depth")
    axes[0].set_xticks(depths)

    axes[1].bar(depths, [results[k]["mean_epoch_t"]*1000 for k in depths], color="coral")
    axes[1].set_xlabel("Depth"); axes[1].set_ylabel("ms / epoch")
    axes[1].set_title("Training Time per Epoch")
    axes[1].set_xticks(depths)

    axes[2].bar(depths, [results[k]["gap"] for k in depths], color="mediumseagreen")
    axes[2].set_xlabel("Depth"); axes[2].set_ylabel("Train – Val Acc Gap")
    axes[2].set_title("Overfitting Gap")
    axes[2].set_xticks(depths)
    axes[2].axhline(0, color="gray", linewidth=0.8)

    _savefig("631_depth_summary.png")


# ── 6.3.2  Width ablation ──────────────────────────────────────────────────

def sec_632(d: Dataset, n_in: int) -> None:
    print("\n[6.3.2] Width ablation")
    widths = [8, 16, 32, 64, 128, 256]
    results: Dict[int, dict] = {}

    for w in widths:
        ls = [n_in, w, w, 1]
        m = _build(d, ls, ["relu", "relu", "sigmoid"])
        h = _train(m, d, track_grads=False, track_dead=False)
        test_acc  = _acc(m, d)
        n_params  = _count_params(ls)
        results[w] = dict(test_acc=test_acc, n_params=n_params)
        print(f"  width={w:>3}  params={n_params:>6}  test_acc={test_acc:.4f}")

    params  = [results[w]["n_params"]  for w in widths]
    accs    = [results[w]["test_acc"]  for w in widths]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogx(params, accs, marker="o", color="steelblue", linewidth=1.5)
    for w, p, a in zip(widths, params, accs):
        ax.annotate(f"w={w}", (p, a), textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel("Number of Parameters (log scale)")
    ax.set_ylabel("Test Accuracy")
    ax.set_title("Width Ablation: Test Accuracy vs Parameters")
    ax.grid(True, which="both", alpha=0.3)
    _savefig("632_width_summary.png")


# ── 6.3.3  Activation comparison ──────────────────────────────────────────

def sec_633(d: Dataset, n_in: int) -> None:
    print("\n[6.3.3] Activation comparison")
    configs = {
        "sigmoid-all":   (["sigmoid",    "sigmoid",    "sigmoid"],   "cross_entropy"),
        "tanh-all":      (["tanh",       "tanh",       "sigmoid"],   "cross_entropy"),
        "relu-sig":      (["relu",       "relu",       "sigmoid"],   "cross_entropy"),
        "lrelu-sig":     (["leaky_relu", "leaky_relu", "sigmoid"],   "cross_entropy"),
    }
    histories: Dict[str, dict] = {}

    for name, (acts, loss) in configs.items():
        m = _build(d, [n_in, 64, 64, 1], acts, loss=loss)
        h = _train(m, d, track_grads=True, track_dead=True)
        test_acc = _acc(m, d)
        histories[name] = dict(h=h, test_acc=test_acc)
        print(f"  {name:<14}  test_acc={test_acc:.4f}")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, (name, res) in zip(axes.ravel(), histories.items()):
        h = res["h"]
        ep = range(1, len(h["train_loss"]) + 1)
        ax.plot(ep, h["train_loss"], label="train")
        ax.plot(ep, h["val_loss"],   label="val")
        ax.set_title(f"{name}  (test acc={res['test_acc']:.3f})")
        ax.set_xlabel("Epoch"); ax.set_ylabel("Loss"); ax.legend()
    _savefig("633_activation_loss.png")

    # gradient statistics over training
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, (name, res) in zip(axes.ravel(), histories.items()):
        h = res["h"]
        if not h["grad_abs_mean"] or not h["grad_abs_mean"][0]:
            ax.set_title(f"{name} – no grad data"); continue
        n_layers = len(h["grad_abs_mean"][0])
        ep = range(1, len(h["grad_abs_mean"]) + 1)
        for l in range(n_layers):
            vals = [row[l] for row in h["grad_abs_mean"]]
            ax.plot(ep, vals, label=f"Layer {l+1}")
        ax.set_title(f"{name} – |grad| mean per layer")
        ax.set_xlabel("Epoch"); ax.set_ylabel("|grad| mean"); ax.legend(fontsize=7)
    _savefig("633_grad_stats.png")

    # dead neuron analysis (ReLU variants only)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, name in zip(axes, ["relu-sig", "lrelu-sig"]):
        h = histories[name]["h"]
        if not h["dead_frac"] or not h["dead_frac"][0]:
            continue
        ep = range(1, len(h["dead_frac"]) + 1)
        n_layers = len(h["dead_frac"][0])
        for l in range(n_layers):
            vals = [row[l] for row in h["dead_frac"]]
            ax.plot(ep, vals, label=f"Hidden {l+1}")
        ax.set_title(f"{name} – Dead Neuron Fraction")
        ax.set_xlabel("Epoch"); ax.set_ylabel("Fraction dead"); ax.legend()
    _savefig("633_dead_neurons.png")

    # vanishing gradient: compare sigmoid vs relu per layer at last epoch
    names_cmp = ["sigmoid-all", "relu-sig"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, name in zip(axes, names_cmp):
        h = histories[name]["h"]
        if not h["grad_abs_mean"]:
            continue
        last = h["grad_abs_mean"][-1]
        ax.bar(range(1, len(last)+1), last, color="steelblue")
        ax.set_title(f"{name} – |grad| at last epoch")
        ax.set_xlabel("Layer"); ax.set_ylabel("|grad| mean")
        ax.set_xticks(range(1, len(last)+1))
    _savefig("633_vanishing_grad.png")


# ── 6.4  Loss function analysis ────────────────────────────────────────────

def sec_64(d: Dataset, n_in: int) -> None:
    print("\n[6.4] Loss function analysis")
    ls   = [n_in, 64, 64, 1]

    configs = {
        "cross_entropy": dict(acts=["relu","relu","sigmoid"], loss="cross_entropy",
                              y_tr=d.y_train, y_v=d.y_val, y_te=d.y_test),
        "mse":           dict(acts=["relu","relu","sigmoid"], loss="mse",
                              y_tr=d.y_train, y_v=d.y_val, y_te=d.y_test),
        "hinge":         dict(acts=["relu","relu","linear"],  loss="hinge",
                              y_tr=_hinge_labels(d.y_train),
                              y_v =_hinge_labels(d.y_val),
                              y_te=_hinge_labels(d.y_test)),
    }

    histories: Dict[str, dict] = {}
    for name, cfg in configs.items():
        m = _build(d, ls, cfg["acts"], loss=cfg["loss"])
        h = m.fit(d.X_train, cfg["y_tr"], d.X_val, cfg["y_v"],
                  epochs=EPOCHS, verbose=False, track_grads=False, track_dead=False)
        ev = m.evaluate(d.X_test, cfg["y_te"])
        histories[name] = dict(h=h, test_acc=ev["acc"])
        print(f"  {name:<15}  test_acc={ev['acc']:.4f}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, (name, res) in zip(axes, histories.items()):
        h = res["h"]
        ep = range(1, len(h["train_loss"]) + 1)
        ax.plot(ep, h["train_loss"], label="train")
        ax.plot(ep, h["val_loss"],   label="val")
        ax.set_title(f"{name}  (test acc={res['test_acc']:.3f})")
        ax.set_xlabel("Epoch"); ax.set_ylabel("Loss"); ax.legend()
    _savefig("64_loss_comparison.png")

    # bar chart of test accuracy
    fig, ax = plt.subplots(figsize=(6, 4))
    names = list(histories.keys())
    accs  = [histories[n]["test_acc"] for n in names]
    ax.bar(names, accs, color=["steelblue","coral","mediumseagreen"])
    ax.set_ylabel("Test Accuracy"); ax.set_title("Test Accuracy by Loss Function")
    for i, v in enumerate(accs):
        ax.text(i, v + 0.002, f"{v:.3f}", ha="center", fontsize=10)
    _savefig("64_loss_bar.png")


# ── 6.5  Optimizer comparison ──────────────────────────────────────────────

def sec_65(d: Dataset, n_in: int) -> None:
    print("\n[6.5] Optimizer comparison")
    ls   = [n_in, 64, 64, 1]
    acts = ["relu", "relu", "sigmoid"]
    BASE_LR = 0.01

    optimizers = ["sgd", "momentum", "adam", "adagrad", "nesterov", "rmsprop", "muon"]
    colors = plt.cm.tab10(np.linspace(0, 0.9, len(optimizers)))
    results: Dict[str, dict] = {}

    for opt in optimizers:
        m = _build(d, ls, acts, optimizer=opt, lr=BASE_LR)
        t0 = time.perf_counter()
        h  = _train(m, d, track_grads=False, track_dead=False)
        elapsed = time.perf_counter() - t0
        test_acc = _acc(m, d)

        # time to reach 90% of best val acc
        best_val = max(h["val_acc"])
        target   = 0.9 * best_val
        t90 = None
        for i, (a, et) in enumerate(zip(h["val_acc"], h["epoch_time_sec"])):
            if a >= target:
                t90 = sum(h["epoch_time_sec"][:i+1])
                break

        results[opt] = dict(h=h, test_acc=test_acc, total_time=elapsed, t90=t90)
        print(f"  {opt:<10}  test_acc={test_acc:.4f}  t90={t90:.2f}s" if t90 else
              f"  {opt:<10}  test_acc={test_acc:.4f}  t90=N/A")

    # convergence curves
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for (opt, res), col in zip(results.items(), colors):
        h  = res["h"]
        ep = range(1, len(h["val_loss"]) + 1)
        axes[0].plot(ep, h["val_loss"], label=opt, color=col)
        axes[1].plot(ep, h["val_acc"],  label=opt, color=col)
    axes[0].set_title("Val Loss – Optimizer Comparison")
    axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("Val Loss"); axes[0].legend(fontsize=8)
    axes[1].set_title("Val Accuracy – Optimizer Comparison")
    axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("Val Accuracy"); axes[1].legend(fontsize=8)
    _savefig("65_optimizer_convergence.png")

    # time to 90% best val acc bar chart
    fig, ax = plt.subplots(figsize=(8, 4))
    t90s = [results[o]["t90"] if results[o]["t90"] else float("nan") for o in optimizers]
    ax.bar(optimizers, t90s, color=colors)
    ax.set_ylabel("Seconds"); ax.set_title("Time to Reach 90% of Best Val Accuracy")
    ax.tick_params(axis="x", rotation=30)
    _savefig("65_time_to_90pct.png")

    # update norm per layer (average over training)
    fig, axes = plt.subplots(2, 4, figsize=(20, 8))
    for ax, (opt, res) in zip(axes.ravel(), results.items()):
        h = res["h"]
        if not h["update_norm"] or not h["update_norm"][0]:
            continue
        n_layers = len(h["update_norm"][0])
        ep = range(1, len(h["update_norm"]) + 1)
        for l in range(n_layers):
            vals = [row[l] for row in h["update_norm"]]
            ax.plot(ep, vals, label=f"W{l+1}")
        ax.set_title(f"{opt} – update norms")
        ax.set_xlabel("Epoch"); ax.legend(fontsize=7)
    axes.ravel()[-1].set_visible(False)
    _savefig("65_update_norms.png")

    # LR sensitivity
    print("  LR sensitivity sweep...")
    lrs = [1e-4, 5e-4, 1e-3, 5e-3, 1e-2, 5e-2, 1e-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    for opt, col in zip(optimizers, colors):
        acc_per_lr = []
        for lr in lrs:
            m2 = _build(d, ls, acts, optimizer=opt, lr=lr)
            m2.fit(d.X_train, d.y_train, d.X_val, d.y_val,
                   epochs=60, verbose=False, track_grads=False, track_dead=False)
            acc_per_lr.append(_acc(m2, d))
        ax.semilogx(lrs, acc_per_lr, marker="o", label=opt, color=col)
    ax.set_xlabel("Learning Rate (log scale)")
    ax.set_ylabel("Test Accuracy")
    ax.set_title("LR Sensitivity per Optimizer")
    ax.legend(fontsize=8); ax.grid(True, which="both", alpha=0.3)
    _savefig("65_lr_sensitivity.png")


# ── 6.6  Regularization ───────────────────────────────────────────────────

def sec_66(d: Dataset, n_in: int) -> None:
    print("\n[6.6] Regularization")
    ls   = [n_in, 64, 64, 1]
    acts = ["relu", "relu", "sigmoid"]
    lams = [0.001, 0.01, 0.1]

    configs = [("none", None, 0.0)]
    for lam in lams:
        configs.append((f"L1_{lam}", "l1", lam))
    for lam in lams:
        configs.append((f"L2_{lam}", "l2", lam))

    results: Dict[str, dict] = {}
    for name, reg, lam in configs:
        m = _build(d, ls, acts, reg=reg, lam=lam)
        h = _train(m, d, track_grads=False, track_dead=False)
        test_acc = _acc(m, d)
        # weight sparsity: fraction of |w| < 1e-3
        all_w = np.concatenate([v.ravel() for k, v in m.params.items() if k.startswith("W")])
        sparsity = float(np.mean(np.abs(all_w) < 1e-3))
        results[name] = dict(h=h, test_acc=test_acc, sparsity=sparsity)
        print(f"  {name:<12}  test_acc={test_acc:.4f}  sparsity={sparsity:.4f}")

    # train vs val accuracy per config
    n_cols = 4
    n_rows = (len(configs) + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 4 * n_rows))
    for ax, (name, reg, lam) in zip(axes.ravel(), configs):
        h  = results[name]["h"]
        ep = range(1, len(h["train_acc"]) + 1)
        ax.plot(ep, h["train_acc"], label="train")
        ax.plot(ep, h["val_acc"],   label="val")
        ax.set_title(f"{name}  acc={results[name]['test_acc']:.3f}")
        ax.set_xlabel("Epoch"); ax.set_ylabel("Acc"); ax.legend(fontsize=7)
    for ax in axes.ravel()[len(configs):]:
        ax.set_visible(False)
    _savefig("66_reg_curves.png")

    # L1 sparsity vs lambda
    l1_lams = lams
    l1_spar = [results[f"L1_{lam}"]["sparsity"] for lam in l1_lams]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(l1_lams, l1_spar, marker="o", color="steelblue")
    ax.set_xscale("log")
    ax.set_xlabel("λ (log scale)"); ax.set_ylabel("Sparsity (|w|<1e-3)")
    ax.set_title("L1 Weight Sparsity vs λ")
    ax.grid(True, which="both", alpha=0.3)
    _savefig("66_l1_sparsity.png")


# ── 6.7  Success analysis ─────────────────────────────────────────────────

def sec_67(d: Dataset, n_in: int) -> None:
    print("\n[6.7] Success analysis")
    ls_mlp   = [n_in, 64, 64, 1]
    acts_mlp = ["relu", "relu", "sigmoid"]

    # best MLP
    m_mlp = _build(d, ls_mlp, acts_mlp, optimizer="adam", lr=0.01)
    _train(m_mlp, d, track_grads=False, track_dead=False)
    mlp_acc = _acc(m_mlp, d)
    print(f"  MLP test_acc={mlp_acc:.4f}")

    # Adaline: single-layer logistic regression
    m_ada = _build(d, [n_in, 1], ["sigmoid"], loss="cross_entropy",
                   optimizer="sgd", lr=0.01)
    _train(m_ada, d, track_grads=False, track_dead=False)
    ada_acc = _acc(m_ada, d)
    print(f"  Adaline test_acc={ada_acc:.4f}")

    # comparison table
    print("\n  ┌──────────────┬────────────────┐")
    print("  │ Model        │   Test Acc     │")
    print("  ├──────────────┼────────────────┤")
    print(f"  │ Adaline      │   {ada_acc:.4f}       │")
    print(f"  │ MLP (2×64)   │   {mlp_acc:.4f}       │")
    print("  └──────────────┴────────────────┘")

    # bar chart
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(["Adaline", "MLP (2×64)"], [ada_acc, mlp_acc],
           color=["coral", "steelblue"])
    ax.set_ylabel("Test Accuracy"); ax.set_title("MLP vs Adaline")
    for i, v in enumerate([ada_acc, mlp_acc]):
        ax.text(i, v + 0.002, f"{v:.4f}", ha="center", fontsize=11)
    _savefig("67_mlp_vs_adaline.png")

    # hidden layer PCA visualisation
    # extract layer-1 and layer-2 activations
    A_all, _ = m_mlp.forward(np.vstack([d.X_train, d.X_val, d.X_test]))
    y_all    = np.vstack([d.y_train, d.y_val, d.y_test]).reshape(-1)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, layer_idx, title in zip(axes, [1, 2], ["Layer 1 Activations", "Layer 2 Activations"]):
        H = A_all[layer_idx]
        comps = fit_pca(H, n_components=2)
        H2    = apply_pca(H, comps)
        sc = ax.scatter(H2[:, 0], H2[:, 1], c=y_all, cmap="bwr", s=5, alpha=0.5)
        plt.colorbar(sc, ax=ax, label="class")
        ax.set_title(f"{title} (PCA 2D)")
        ax.set_xlabel("PC 1"); ax.set_ylabel("PC 2")
    _savefig("67_pca_activations.png")


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading data...")
    d    = prepare(CSV, seed=SEED)
    n_in = d.X_train.shape[1]
    print(f"  features={n_in}  train={d.X_train.shape[0]}  "
          f"val={d.X_val.shape[0]}  test={d.X_test.shape[0]}")

    sec_631(d, n_in)
    sec_632(d, n_in)
    sec_633(d, n_in)
    sec_64(d, n_in)
    sec_65(d, n_in)
    sec_66(d, n_in)
    sec_67(d, n_in)

    print(f"\nAll done — outputs in {OUT}/")


if __name__ == "__main__":
    main()