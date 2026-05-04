import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# Activation Functions 

def sigmoid(z):
    z = np.clip(z, -500.0, 500.0)
    return 1.0 / (1.0 + np.exp(-z))

def sigmoid_deriv(a):
    return a * (1.0 - a)

def tanh(z):
    z = np.clip(z, -500.0, 500.0)
    e_pos, e_neg = np.exp(z), np.exp(-z)
    return (e_pos - e_neg) / (e_pos + e_neg)

def tanh_deriv(a):
    return 1.0 - np.power(a, 2)

def linear(z):
    return z

def linear_deriv(z):
    return np.ones_like(z)

def apply_activation(name, z):
    return {"sigmoid": sigmoid, "tanh": tanh, "linear": linear}[name](z)

def apply_deriv(name, z, a):
    if name == "sigmoid": return sigmoid_deriv(a)
    if name == "tanh":    return tanh_deriv(a)
    return linear_deriv(z)


# Loss Functions

def bce(y_true, y_pred):
    p = np.clip(y_pred, 1e-12, 1 - 1e-12)
    return float(-np.mean(y_true * np.log(p) + (1 - y_true) * np.log(1 - p)))

# Combined BCE + sigmoid gradient
def bce_grad(y_true, y_pred):
    return (y_pred - y_true) / y_true.shape[0]

# 0.5 * MSE for clean gradient
def mse(y_true, y_pred):
    return float(0.5 * np.mean(np.power(y_pred - y_true, 2)))

def mse_grad(y_true, y_pred):
    return (y_pred - y_true) / y_true.shape[0]


# Dataset 

def make_dataset(task, n=500, noise=0.1, seed=42):
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, (n, 2)).astype(float)
    X = bits + rng.normal(0, noise, (n, 2))

    if task == "xor":
        y = np.logical_xor(bits[:, 0] > 0.5, bits[:, 1] > 0.5).astype(float).reshape(-1, 1)
    else:
        y = np.cos(2.0 * X[:, 0] + X[:, 1]).reshape(-1, 1)
    return X.astype(float), y

def train_test_split(X, y, test_ratio=0.2, seed=42):
    rng = np.random.default_rng(seed)
    idx = np.arange(X.shape[0])
    rng.shuffle(idx)
    n_test = int(round(test_ratio * len(idx)))
    return X[idx[n_test:]], X[idx[:n_test]], y[idx[n_test:]], y[idx[:n_test]]


# Model 

class ANN:
    """Two-layer ANN: Input(d) → Hidden(h, tanh) → Output(1, sigmoid or linear)."""

    def __init__(self, input_dim=2, hidden_dim=2, output_dim=1,
                 h_act="tanh", o_act="sigmoid", loss="bce", lr=0.05, seed=42):
        self.h_act, self.o_act, self.loss_name, self.lr = h_act, o_act, loss, lr
        rng = np.random.default_rng(seed)

        def glorot(fi, fo):
            lim = np.sqrt(6.0 / (fi + fo))
            return rng.uniform(-lim, lim, (fi, fo))

        self.W1, self.b1 = glorot(input_dim, hidden_dim), np.zeros(hidden_dim)
        self.W2, self.b2 = glorot(hidden_dim, output_dim), np.zeros(output_dim)

    def forward(self, X):
        z1 = X @ self.W1 + self.b1
        a1 = apply_activation(self.h_act, z1)
        z2 = a1 @ self.W2 + self.b2
        yp = apply_activation(self.o_act, z2)
        return yp, {"X": X, "z1": z1, "a1": a1, "z2": z2, "yp": yp}

    def compute_loss(self, y, yp):
        return bce(y, yp) if self.loss_name == "bce" else mse(y, yp)

    def backward(self, cache, y):
        X, z1, a1, z2, yp = cache["X"], cache["z1"], cache["a1"], cache["z2"], cache["yp"]

        if self.loss_name == "bce":
            dz2 = bce_grad(y, yp)
        else:
            dz2 = mse_grad(y, yp) * apply_deriv(self.o_act, z2, yp)

        dW2 = a1.T @ dz2
        db2 = np.sum(dz2, axis=0)
        dz1 = (dz2 @ self.W2.T) * apply_deriv(self.h_act, z1, a1)
        dW1 = X.T @ dz1
        db1 = np.sum(dz1, axis=0)
        return {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2}

    def step(self, grads):
        for p in ("W1", "b1", "W2", "b2"):
            setattr(self, p, getattr(self, p) - self.lr * grads[p])

    def predict(self, X):
        yp, _ = self.forward(X)
        return yp


# Metrics & Training 

def accuracy(y, yp, task, tol=0.1):
    if task == "xor":
        return float(np.mean((yp >= 0.5).astype(float) == y))
    return float(np.mean(np.abs(yp - y) < tol))

def train(model, Xtr, ytr, Xte, yte, epochs, batch_size, task, seed=42, log_every=None):
    rng = np.random.default_rng(seed)
    hist = {"trl": [], "tel": [], "tra": [], "tea": []}
    log_every = log_every or max(1, epochs // 10)

    for ep in range(1, epochs + 1):
        n = Xtr.shape[0]
        if batch_size >= n:  # Deterministic GD
            yp, cache = model.forward(Xtr)
            model.step(model.backward(cache, ytr))
        else:                # Mini-batch SGD
            idx = np.arange(n)
            rng.shuffle(idx)
            for s in range(0, n, batch_size):
                b = idx[s:s + batch_size]
                yp_b, cache_b = model.forward(Xtr[b])
                model.step(model.backward(cache_b, ytr[b]))

        yp_tr, yp_te = model.predict(Xtr), model.predict(Xte)
        trl = model.compute_loss(ytr, yp_tr)
        tel = model.compute_loss(yte, yp_te)
        tra = accuracy(ytr, yp_tr, task)
        tea = accuracy(yte, yp_te, task)

        hist["trl"].append(trl); hist["tel"].append(tel)
        hist["tra"].append(tra); hist["tea"].append(tea)

        if ep % log_every == 0 or ep == epochs:
            print(f"epoch {ep}/{epochs}  loss {trl:.4f}/{tel:.4f}  acc {tra:.4f}/{tea:.4f}")

    return hist


# Plotting 

def _save_fig(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"saved {path}")

def plot_main(hist, task, out_dir, tag):
    os.makedirs(out_dir, exist_ok=True)
    acc_lbl = "Accuracy" if task == "xor" else "Accuracy (tol=0.1)"
    ep = range(1, len(hist["trl"]) + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle(f"{task.upper()} — Training Curves", fontsize=13)

    ax1.plot(ep, hist["trl"], label="Train Loss")
    ax1.plot(ep, hist["tel"], label="Test Loss", linestyle="--")
    ax1.set_xlabel("Epoch"); ax1.set_ylabel("Loss"); ax1.set_title("Loss"); ax1.legend()

    ax2.plot(ep, hist["tra"], label="Train Acc")
    ax2.plot(ep, hist["tea"], label="Test Acc", linestyle="--")
    ax2.set_xlabel("Epoch"); ax2.set_ylabel(acc_lbl); ax2.set_title(acc_lbl); ax2.legend()

    _save_fig(fig, os.path.join(out_dir, f"{tag}_curves.png"))

def plot_sweep(all_hists, labels, task, out_dir, filename, title):
    os.makedirs(out_dir, exist_ok=True)
    acc_lbl = "Accuracy" if task == "xor" else "Accuracy (tol=0.1)"
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4))
    fig.suptitle(title, fontsize=13)

    for i, (hist, lbl) in enumerate(zip(all_hists, labels)):
        ep = range(1, len(hist["trl"]) + 1)
        c = colors[i % len(colors)]
        ax1.plot(ep, hist["trl"], color=c, label=f"{lbl} train")
        ax1.plot(ep, hist["tel"], color=c, linestyle="--", label=f"{lbl} test")
        ax2.plot(ep, hist["tra"], color=c, label=f"{lbl} train")
        ax2.plot(ep, hist["tea"], color=c, linestyle="--", label=f"{lbl} test")

    ax1.set_xlabel("Epoch"); ax1.set_ylabel("Loss");   ax1.set_title("Loss");   ax1.legend(fontsize=8)
    ax2.set_xlabel("Epoch"); ax2.set_ylabel(acc_lbl); ax2.set_title(acc_lbl); ax2.legend(fontsize=8)

    _save_fig(fig, os.path.join(out_dir, filename))


# Experiment Runners

def build_model(task, hidden_dim, lr, seed):
    if task == "xor":
        return ANN(2, hidden_dim, 1, "tanh", "sigmoid", "bce", lr, seed)
    return ANN(2, hidden_dim, 1, "tanh", "linear", "mse", lr, seed)

def _run_and_report(task, n, batch_size, hidden_dim, lr, epochs, noise, seed, log_every):
    X, y = make_dataset(task, n, noise, seed)
    Xtr, Xte, ytr, yte = train_test_split(X, y, 0.2, seed)
    mode = "det-gd" if batch_size >= Xtr.shape[0] else f"sgd-b{batch_size}"
    print(f"\n{task} | n={n} | {mode} | hidden={hidden_dim} | lr={lr}")

    model = build_model(task, hidden_dim, lr, seed)
    hist = train(model, Xtr, ytr, Xte, yte, epochs, batch_size, task, seed, log_every)

    yp_tr, yp_te = model.predict(Xtr), model.predict(Xte)
    trl = model.compute_loss(ytr, yp_tr); tel = model.compute_loss(yte, yp_te)
    tra = accuracy(ytr, yp_tr, task);     tea = accuracy(yte, yp_te, task)

    print(f"  train  loss {trl:.4f}  acc {tra:.4f}")
    print(f"  test   loss {tel:.4f}  acc {tea:.4f}")
    return hist, {"trl": trl, "tel": tel, "tra": tra, "tea": tea}

def run_main(task, n, batch_size, hidden_dim, lr, epochs, noise, seed, out_dir):
    hist, _ = _run_and_report(task, n, batch_size, hidden_dim, lr, epochs, noise, seed,
                               log_every=max(1, epochs // 10))
    plot_main(hist, task, out_dir, f"{task}_main_n{n}_bs{batch_size}")

def experiment_gd_sweep(task, n_list, hidden_dim, lr, epochs, noise, seed, out_dir):
    print(f"\ngd sweep  task={task}  n={n_list}")
    all_hists, summary = [], []
    for n in n_list:
        hist, res = _run_and_report(task, n, 10**9, hidden_dim, lr, epochs, noise, seed,
                                    log_every=max(1, epochs // 5))
        all_hists.append(hist)
        summary.append((n, res))

    plot_sweep(all_hists, [f"n={n}" for n in n_list], task, out_dir,
               f"{task}_gd_sweep.png",
               f"{task.upper()} — Deterministic GD: effect of dataset size n")

    print(f"\n{'n':>8}  {'test_loss':>10}  {'test_acc':>10}")
    for n, r in summary:
        print(f"{n:>8}  {r['tel']:>10.4f}  {r['tea']:>10.4f}")

def experiment_sgd_sweep(task, n, m_list, hidden_dim, lr, epochs, noise, seed, out_dir):
    print(f"\nsgd sweep  task={task}  n={n}  batches={m_list}")
    all_hists, summary = [], []
    for m in m_list:
        hist, res = _run_and_report(task, n, m, hidden_dim, lr, epochs, noise, seed,
                                    log_every=max(1, epochs // 5))
        all_hists.append(hist)
        summary.append((m, res))

    plot_sweep(all_hists, [f"batch={m}" for m in m_list], task, out_dir,
               f"{task}_sgd_sweep.png",
               f"{task.upper()} — SGD: effect of batch size m  (n={n})")

    print(f"\n{'batch':>8}  {'test_loss':>10}  {'test_acc':>10}")
    for m, r in summary:
        print(f"{m:>8}  {r['tel']:>10.4f}  {r['tea']:>10.4f}")


# Entry Point 
def parse_list(s):
    return [int(x) for x in s.split(",") if x.strip()]

def main():
    p = argparse.ArgumentParser(description="ANN with Backpropagation")
    p.add_argument("--task",       choices=["xor", "cosine"], default="xor")
    p.add_argument("--experiment", choices=["main", "gd_sweep", "sgd_sweep"], default="main")
    p.add_argument("--n",          type=int,   default=500)
    p.add_argument("--n_list",     type=str,   default="100,500,1000")
    p.add_argument("--batch_size", type=int,   default=32)
    p.add_argument("--m_list",     type=str,   default="1,16,128")
    p.add_argument("--hidden_dim", type=int,   default=2)
    p.add_argument("--lr",         type=float, default=0.05)
    p.add_argument("--epochs",     type=int,   default=300)
    p.add_argument("--noise",      type=float, default=0.1)
    p.add_argument("--seed",       type=int,   default=42)
    p.add_argument("--out_dir",    type=str,   default="outputs")
    args = p.parse_args()

    epochs = args.epochs if args.task == "xor" else max(args.epochs, 500)

    if args.experiment == "main":
        run_main(args.task, args.n, args.batch_size, args.hidden_dim,
                 args.lr, epochs, args.noise, args.seed, args.out_dir)
    elif args.experiment == "gd_sweep":
        experiment_gd_sweep(args.task, parse_list(args.n_list), args.hidden_dim,
                            args.lr, epochs, args.noise, args.seed, args.out_dir)
    elif args.experiment == "sgd_sweep":
        experiment_sgd_sweep(args.task, args.n, parse_list(args.m_list), args.hidden_dim,
                             args.lr, epochs, args.noise, args.seed, args.out_dir)

if __name__ == "__main__":
    main()