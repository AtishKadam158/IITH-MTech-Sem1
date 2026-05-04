#!/usr/bin/env python3
import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from adaline import Adaline


# Column schema 

ALL_COLS = [
    "student_id", "day_of_week", "meal_time", "meal_type",
    "is_weekend", "class_day", "assignment_deadline",
    "temperature_c", "humidity", "wind_speed", "rain_mm",
    "air_quality_index", "rising_time_min", "sleeping_time_min",
    "mess_duration_min",
]

DISCRETE_COLS = {
    "student_id", "day_of_week", "meal_time", "meal_type",
    "is_weekend", "class_day", "assignment_deadline",
    "rising_time_min", "sleeping_time_min",
}


# Data loading

def read_csv(path):
    """Parse CSV into a column-keyed dict of numpy arrays."""
    with open(path, "r", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    columns = {}
    for col in ALL_COLS:
        arr = np.array([float(r[col]) for r in rows])
        if col in DISCRETE_COLS:
            arr = arr.astype(int)
        columns[col] = arr
    return columns


# Feature engineering

def encode_onehot(arr, num_classes):
    """Return a (n, num_classes) indicator matrix."""
    out = np.zeros((len(arr), num_classes), dtype=float)
    out[np.arange(len(arr)), arr.astype(int)] = 1.0
    return out


NUMERIC_COLS = [
    "meal_type", "is_weekend", "class_day", "assignment_deadline",
    "temperature_c", "humidity", "wind_speed", "rain_mm",
    "air_quality_index", "rising_time_min", "sleeping_time_min",
]


def make_features(columns):
    """
    Assemble feature matrix X and regression target y.
    day_of_week → 7-dim one-hot, meal_time → 3-dim one-hot,
    remaining columns appended as-is.
    """
    n = len(columns["mess_duration_min"])
    blocks = [
        encode_onehot(columns["day_of_week"], 7),
        encode_onehot(columns["meal_time"],   3),
    ]
    for col in NUMERIC_COLS:
        blocks.append(columns[col].reshape(n, 1).astype(float))

    X = np.concatenate(blocks, axis=1)
    y = columns["mess_duration_min"].astype(float)
    return X, y


# Preprocessing

def train_val_test_split(n, seed=42, val_frac=0.2, test_frac=0.2):
    """Shuffle indices and return (train, val, test) index arrays."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_test = int(round(test_frac * n))
    n_val  = int(round(val_frac  * (n - n_test)))
    return idx[n_test + n_val:], idx[n_test: n_test + n_val], idx[:n_test]


def z_normalise(X_train, X_val, X_test):
    """Standardise using train-set statistics only."""
    mu  = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std = np.where(std < 1e-12, 1.0, std)   # avoid division by zero
    return (X_train-mu)/std, (X_val-mu)/std, (X_test-mu)/std, mu, std


def scale(X, mu, std):
    return (X - mu) / std


# PCA (numpy only) 

def pca_fit(X, k=2):
    """Compute top-k principal components from the covariance matrix."""
    cov = (X.T @ X) / (X.shape[0] - 1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    top_k = np.argsort(eigvals)[::-1][:k]
    return eigvecs[:, top_k]


def pca_transform(X, components):
    return X @ components


# Labels & metrics 

def to_binary(y, threshold):
    """Map continuous target to {+1, -1} using a threshold."""
    return np.where(y >= threshold, 1.0, -1.0)


def sign_predict(raw_output):
    """Convert linear ADALINE output to class labels via sign rule."""
    return np.where(raw_output >= 0.0, 1.0, -1.0)


def class_accuracy(y_true, raw_output):
    return float(np.mean(sign_predict(raw_output) == y_true))


# Plot utilities 

ORANGE = "#e87722"
BLUE   = "#2266cc"

def save_plot(filepath):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    plt.close()
    print(f"  [saved] {filepath}")


# Experiment (a): Dataset visualisation 

def run_exp_a(X_pca, y_continuous, y_binary, out_dir):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle("Dataset Visualisation — PCA 2D Projection", fontsize=13)

    # left: continuous target as heatmap
    sc = axes[0].scatter(X_pca[:, 0], X_pca[:, 1],
                         c=y_continuous, cmap="viridis", s=8, alpha=0.7)
    fig.colorbar(sc, ax=axes[0], label="mess_duration_min")
    axes[0].set(xlabel="PC1", ylabel="PC2", title="Coloured by mess duration")

    # right: binary class membership
    point_colours = np.where(y_binary > 0, ORANGE, BLUE)
    axes[1].scatter(X_pca[:, 0], X_pca[:, 1], c=point_colours, s=8, alpha=0.7)
    from matplotlib.patches import Patch
    axes[1].legend(handles=[Patch(color=ORANGE, label="≥ median (+1)"),
                             Patch(color=BLUE,   label="< median (−1)")])
    axes[1].set(xlabel="PC1", ylabel="PC2", title="Coloured by binary class")

    save_plot(os.path.join(out_dir, "dataset_pca.png"))


# Experiment (b): Training curves + decision boundary 

def run_exp_b(X_tr, y_tr, X_va, y_va, X_te, y_te,
              X_tr_2d, X_va_2d, X_te_2d,
              X_full_2d, y_full_binary,
              lr, epochs, out_dir):

    # full-feature model for MSE / accuracy metrics
    full_model = Adaline(learning_rate=lr, max_iterations=epochs)
    full_model.fit(X_tr, y_tr, X_val=X_va, y_val=y_va, verbose=True)

    # 2D model for decision boundary visualisation
    model_2d = Adaline(learning_rate=lr, max_iterations=epochs)
    model_2d.fit(X_tr_2d, y_tr, X_val=X_va_2d, y_val=y_va)

    # report metrics
    for tag, Xp, yp in [("Train", X_tr, y_tr), ("Val", X_va, y_va), ("Test", X_te, y_te)]:
        mse = full_model.score(Xp, yp)
        acc = class_accuracy(yp, full_model.predict(Xp))
        print(f"  {tag:<5}: MSE={mse:.4f}  Acc={acc:.4f}")

    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    fig.suptitle(f"ADALINE Training  (lr={lr}, epochs={epochs})", fontsize=13)
    epochs_range = range(1, len(full_model.mse_train_) + 1)

    # panel 1: training MSE only
    axes[0].plot(epochs_range, full_model.mse_train_, color=ORANGE)
    axes[0].set(xlabel="Epoch", ylabel="MSE", title="MSE vs Epoch (Train)")

    # panel 2: train vs validation MSE
    axes[1].plot(epochs_range, full_model.mse_train_, label="Train", color=ORANGE)
    if full_model.mse_val_:
        axes[1].plot(epochs_range, full_model.mse_val_, label="Val",
                     color=BLUE, linestyle="--")
    axes[1].set(xlabel="Epoch", ylabel="MSE", title="Train vs Validation MSE")
    axes[1].legend()

    # panel 3: decision boundary on PCA 2D projection
    pt_colours = np.where(y_full_binary > 0, ORANGE, BLUE)
    axes[2].scatter(X_full_2d[:, 0], X_full_2d[:, 1], c=pt_colours, s=8, alpha=0.6)
    w0, w1 = float(model_2d.weights_[0]), float(model_2d.weights_[1])
    b = float(model_2d.bias_)
    x_range = np.linspace(X_full_2d[:, 0].min(), X_full_2d[:, 0].max(), 200)
    if abs(w1) > 1e-10:
        # decision line: w0*x + w1*y + b = 0  →  y = -(w0*x + b) / w1
        boundary = -(w0 * x_range + b) / w1
        axes[2].plot(x_range, boundary, color="black", linewidth=1.5,
                     label="Decision boundary")
    axes[2].set(xlabel="PC1", ylabel="PC2", title="Decision Boundary (PCA 2D)")
    axes[2].legend(fontsize=8)

    save_plot(os.path.join(out_dir, "training_curves.png"))
    return full_model


# Experiment (c): Learning-rate sweep 

def run_exp_c(X_tr, y_tr, X_va, y_va, lr_values, epochs, out_dir):
    print(f"\n  Learning-rate sweep: {lr_values}")
    palette = ["#1a6faf", ORANGE, "#2ab22a", "#cc2222"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    fig.suptitle("ADALINE — Learning-Rate Sweep", fontsize=13)

    for i, lr in enumerate(lr_values):
        colour = palette[i % len(palette)]
        m = Adaline(learning_rate=lr, max_iterations=epochs)
        m.fit(X_tr, y_tr, X_val=X_va, y_val=y_va)

        # skip plotting if weights diverged (nan, inf, or astronomically large)
        if not np.isfinite(m.mse_train_[-1]) or m.mse_train_[-1] > 1e6:
            print(f"  lr={lr:<6}  DIVERGED (overflow) — skipped in plot")
            axes[0].plot([], [], label=f"η={lr} (diverged)", color=colour, linestyle=":")
            axes[1].plot([], [], label=f"η={lr} (diverged)", color=colour, linestyle=":")
            continue

        ep = range(1, len(m.mse_train_) + 1)
        axes[0].plot(ep, m.mse_train_, label=f"η={lr}", color=colour)
        if m.mse_val_:
            axes[1].plot(ep, m.mse_val_, label=f"η={lr}", color=colour)

        tr_acc = class_accuracy(y_tr, m.predict(X_tr))
        va_acc = class_accuracy(y_va, m.predict(X_va)) if X_va is not None else float("nan")
        print(f"  lr={lr:<6}  final_train_mse={m.mse_train_[-1]:.5f}"
              f"  train_acc={tr_acc:.4f}  val_acc={va_acc:.4f}")

    for ax, title in zip(axes, ["Training MSE", "Validation MSE"]):
        ax.set(xlabel="Epoch", ylabel="MSE", title=title)
        ax.legend()

    save_plot(os.path.join(out_dir, "lr_sweep.png"))


# Experiment (d): Training set size sweep 

def run_exp_d(X_tr, y_tr, X_te, y_te, lr, epochs, out_dir, seed=42):
    # uses full feature matrix (not PCA) so accuracy reflects true model capacity
    print("\n  Training-size sweep (10% → 100%)")
    rng   = np.random.default_rng(seed)
    order = rng.permutation(len(y_tr))

    pct_steps = list(range(10, 101, 10))
    accuracies = []

    for pct in pct_steps:
        k  = max(2, int(round(pct / 100.0 * len(order))))
        Xi = X_tr[order[:k]]
        yi = y_tr[order[:k]]
        m  = Adaline(learning_rate=lr, max_iterations=epochs)
        m.fit(Xi, yi)
        acc = class_accuracy(y_te, m.predict(X_te))
        accuracies.append(acc)
        print(f"  {pct:>4}%  ({k:>5} samples)  test_acc={acc:.4f}")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(pct_steps, accuracies, marker="o", color=ORANGE, linewidth=2)
    ax.set(xlabel="Training Set Size (%)", ylabel="Test Accuracy",
           title="ADALINE: Test Accuracy vs Training Set Size",
           ylim=(0, 1), xticks=pct_steps)
    ax.grid(True, linestyle="--", alpha=0.4)
    save_plot(os.path.join(out_dir, "size_vs_accuracy.png"))


# ── Entry point ───────────────────────────────────────────────────────────────

def locate_csv():
    candidates = [
        "outputs/iith_campus_life_5000.csv",
        "outputs/iith_campus_life_500.csv",
        "../A1_task4/outputs/iith_campus_life_5000.csv",
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


def main():
    ap = argparse.ArgumentParser(description="Task 5 — ADALINE Experiments")
    ap.add_argument("--csv",      type=str,   default="")
    ap.add_argument("--out_dir",  type=str,   default="outputs")
    ap.add_argument("--epochs",   type=int,   default=300)
    ap.add_argument("--lr",       type=float, default=0.1)
    ap.add_argument("--lr_sweep", type=str,   default="0.01,0.1,1.0,10.0")
    ap.add_argument("--seed",     type=int,   default=42)
    args = ap.parse_args()

    csv_path = args.csv.strip() or locate_csv()
    if not csv_path or not os.path.exists(csv_path):
        print("ERROR: dataset CSV not found. Run Task 4 first or pass --csv <path>.")
        sys.exit(1)
    print(f"Loading: {csv_path}")

    lr_values = [float(v) for v in args.lr_sweep.split(",") if v.strip()]

    # load → features
    raw      = read_csv(csv_path)
    X_raw, y_cont = make_features(raw)
    n = X_raw.shape[0]
    print(f"Dataset: {n} samples, {X_raw.shape[1]} features")

    # split → normalise
    tr_idx, va_idx, te_idx = train_val_test_split(n, seed=args.seed)
    X_tr, X_va, X_te, mu, std = z_normalise(
        X_raw[tr_idx], X_raw[va_idx], X_raw[te_idx])
    X_all = scale(X_raw, mu, std)

    # binarise target using train+val median as threshold
    threshold = float(np.median(y_cont[np.concatenate([tr_idx, va_idx])]))
    print(f"Classification threshold (median): {threshold:.2f} min")

    y_all = to_binary(y_cont, threshold)
    y_tr  = y_all[tr_idx]
    y_va  = y_all[va_idx]
    y_te  = y_all[te_idx]

    # PCA — fit on train split only, then apply to all
    pca_vecs  = pca_fit(X_tr, k=2)
    X_all_2d  = pca_transform(X_all, pca_vecs)
    X_tr_2d   = pca_transform(X_tr,  pca_vecs)
    X_va_2d   = pca_transform(X_va,  pca_vecs)
    X_te_2d   = pca_transform(X_te,  pca_vecs)

    os.makedirs(args.out_dir, exist_ok=True)

    print("\n[Experiment a] Dataset PCA visualisation ...")
    run_exp_a(X_all_2d, y_cont, y_all, args.out_dir)

    print("\n[Experiment b] Training ADALINE ...")
    run_exp_b(
        X_tr, y_tr, X_va, y_va, X_te, y_te,
        X_tr_2d, X_va_2d, X_te_2d,
        X_all_2d, y_all,
        lr=args.lr, epochs=args.epochs,
        out_dir=args.out_dir,
    )

    print("\n[Experiment c] Learning-rate sweep ...")
    run_exp_c(X_tr, y_tr, X_va, y_va, lr_values, args.epochs, args.out_dir)

    print("\n[Experiment d] Training-size sweep ...")
    run_exp_d(X_tr, y_tr, X_te, y_te,
              lr=args.lr, epochs=args.epochs,
              out_dir=args.out_dir, seed=args.seed)

    print(f"\n{'='*50}")
    print(f"  Plots saved to: {os.path.abspath(args.out_dir)}")
    print(f"  dataset_pca.png  |  training_curves.png  |  lr_sweep.png  |  size_vs_accuracy.png")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()