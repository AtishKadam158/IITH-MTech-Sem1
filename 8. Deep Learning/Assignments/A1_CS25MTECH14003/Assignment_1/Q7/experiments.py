import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from kernels import (
    MLP, KernelSVR,
    linear_kernel, polynomial_kernel, rbf_kernel, neural_kernel,
    linear_kernel_matrix, poly_kernel_matrix, rbf_kernel_matrix, neural_kernel_matrix,
    compute_kernel_matrix,
)

np.random.seed(42)
os.makedirs("outputs", exist_ok=True)



def normalize(X, mean=None, std=None):
    if mean is None:
        mean = np.mean(X, axis=0)
    if std is None:
        std = np.std(X, axis=0) + 1e-8
    return (X - mean) / std, mean, std


def train_test_split_manual(X, y, test_ratio=0.2, seed=42):
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    idx = rng.permutation(n)
    n_test = int(n * test_ratio)
    test_idx = idx[:n_test]
    train_idx = idx[n_test:]
    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


# t-SNE (from scratch, numpy only)


class TSNE:
    
    def __init__(self, n_components=2, perplexity=30.0, lr=200.0,
                 n_iter=500, early_exaggeration=4.0, momentum=0.8):
        self.n_components = n_components
        self.perplexity = perplexity
        self.lr = lr
        self.n_iter = n_iter
        self.early_exaggeration = early_exaggeration
        self.momentum = momentum

    def _pairwise_sq_dist(self, X):
        sq = np.sum(X ** 2, axis=1)
        return sq[:, None] + sq[None, :] - 2.0 * X.dot(X.T)

    def _compute_p(self, X):
        n = X.shape[0]
        D2 = self._pairwise_sq_dist(X)
        np.fill_diagonal(D2, np.inf)

        P = np.zeros((n, n))
        target_entropy = np.log(self.perplexity)

        for i in range(n):
            beta_lo, beta_hi = -np.inf, np.inf
            beta = 1.0
            di = D2[i]
            for _ in range(50):
                e = np.exp(-di * beta)
                e_sum = np.sum(e) + 1e-12
                H = np.log(e_sum) + beta * np.sum(di * e) / e_sum
                if np.abs(H - target_entropy) < 1e-5:
                    break
                if H > target_entropy:
                    beta_lo = beta
                    beta = beta * 2 if beta_hi == np.inf else (beta + beta_hi) / 2
                else:
                    beta_hi = beta
                    beta = beta / 2 if beta_lo == -np.inf else (beta + beta_lo) / 2
                e = np.exp(-di * beta)
                e_sum = np.sum(e) + 1e-12
            P[i] = e / e_sum
            P[i, i] = 0.0

        P = (P + P.T) / (2 * n)
        P = np.maximum(P, 1e-12)
        return P

    def fit_transform(self, X):
        n = X.shape[0]
        # Pairwise probs in high-D
        P = self._compute_p(X)
        P *= self.early_exaggeration

        # Random init in low-D
        Y = np.random.randn(n, self.n_components) * 1e-4
        vel = np.zeros_like(Y)

        for step in range(self.n_iter):
            # t-distribution Q in low-D
            D2_low = self._pairwise_sq_dist(Y)
            inv_d = 1.0 / (1.0 + D2_low)
            np.fill_diagonal(inv_d, 0.0)
            Q = inv_d / (np.sum(inv_d) + 1e-12)
            Q = np.maximum(Q, 1e-12)

            # Gradient
            PQ = P - Q
            grad = np.zeros_like(Y)
            for i in range(n):
                diff = Y[i] - Y          # (n, d)
                grad[i] = 4.0 * np.sum((PQ[i] * inv_d[i])[:, None] * diff, axis=0)

            # Update with momentum
            vel = self.momentum * vel - self.lr * grad
            Y += vel

            # Remove early exaggeration after 100 steps
            if step == 100:
                P /= self.early_exaggeration

        return Y


# PLOTTING HELPERS

def plot_kernel_matrix(K, title, filename):
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(K, aspect="auto", cmap="viridis")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Sample index")
    ax.set_ylabel("Sample index")
    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(filename, dpi=100)
    plt.close()
    print(f"  Saved: {filename}")


def plot_2d_decision_boundary(X2d, y, y_pred, title, filename):
    """Scatter of true vs predicted in 2-D PCA space."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sc0 = axes[0].scatter(X2d[:, 0], X2d[:, 1], c=y, cmap="plasma", s=10, alpha=0.7)
    axes[0].set_title(f"{title}\nTrue target", fontsize=11)
    axes[0].set_xlabel("PC 1")
    axes[0].set_ylabel("PC 2")
    plt.colorbar(sc0, ax=axes[0])

    sc1 = axes[1].scatter(X2d[:, 1], X2d[:, 1], c=y_pred, cmap="plasma", s=10, alpha=0.7)
    axes[1].set_title(f"{title}\nPredicted target", fontsize=11)
    axes[1].set_xlabel("PC 1")
    axes[1].set_ylabel("PC 2")
    plt.colorbar(sc1, ax=axes[1])

    plt.tight_layout()
    plt.savefig(filename, dpi=100)
    plt.close()
    print(f"  Saved: {filename}")


def pca_project(X, n_components=2):
    """Manual PCA using eigendecomposition (numpy only)."""
    X_centered = X - np.mean(X, axis=0)
    cov = X_centered.T.dot(X_centered) / (X_centered.shape[0] - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Sort descending
    order = np.argsort(eigenvalues)[::-1]
    eigenvectors = eigenvectors[:, order]
    return X_centered.dot(eigenvectors[:, :n_components])


# MAIN PIPELINE

def main():
    
    # 1. Load data
    print("\n")
    print("STEP 1: Loading data")
    print("\n")

    # Load CSV manually
    with open("iith_campus_life_5000.csv", "r") as f:
        lines = f.read().strip().split("\n")

    header = lines[0].split(",")
    print(f"Columns: {header}")
    # Target: mess_duration_min (last column)
    # Features: all except student_id (first) and target (last)

    data = []
    for line in lines[1:]:
        vals = line.split(",")
        if len(vals) == len(header):
            data.append([float(v) for v in vals])
    data = np.array(data)

    # Features: columns 1..-1  (drop student_id at col 0)
    X_all = data[:, 1:-1]
    y_all = data[:, -1]

    print(f"Dataset shape: {X_all.shape}, target shape: {y_all.shape}")
    print(f"Target range: [{y_all.min():.2f}, {y_all.max():.2f}]")

    # Normalize
    X_norm, X_mean, X_std = normalize(X_all)
    y_mean = np.mean(y_all)
    y_std = np.std(y_all) + 1e-8
    y_norm = (y_all - y_mean) / y_std

    # Train / test split
    X_tr, X_te, y_tr, y_te = train_test_split_manual(X_norm, y_norm, test_ratio=0.2)
    print(f"Train: {X_tr.shape}, Test: {X_te.shape}")

    # Phase-4 subset (smaller set for heavy kernel SVR)
    N_SVR = 400   # use 400 training samples for SVR (O(n^2) kernel matrix)
    idx_svr = np.random.choice(X_tr.shape[0], N_SVR, replace=False)
    X_svr_tr = X_tr[idx_svr]
    y_svr_tr = y_tr[idx_svr]
    N_TE_SVR = 150
    idx_te = np.random.choice(X_te.shape[0], N_TE_SVR, replace=False)
    X_svr_te = X_te[idx_te]
    y_svr_te = y_te[idx_te]
    print(f"SVR subset – Train: {X_svr_tr.shape}, Test: {X_svr_te.shape}")

    
    # 2. Train best MLP
    
    print("\n")
    print("STEP 2: Training MLP (from scratch)")
    print("\n")

    n_features = X_tr.shape[1]
    # Best architecture: [14, 256, 128, 64, 1]
    mlp = MLP(
        layer_sizes=[n_features, 256, 128, 64, 1],
        lr=0.002,
        epochs=300,
        batch_size=128,
        verbose=True
    )
    loss_history = mlp.fit(X_tr, y_tr)

    train_r2 = mlp.score(X_tr, y_tr)
    test_r2 = mlp.score(X_te, y_te)
    train_rmse = mlp.rmse(X_tr, y_tr)
    test_rmse = mlp.rmse(X_te, y_te)
    print(f"\nMLP  Train R²={train_r2:.4f}  RMSE={train_rmse:.4f}")
    print(f"MLP  Test  R²={test_r2:.4f}  RMSE={test_rmse:.4f}")

    # Plot training loss
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(loss_history, color="steelblue", linewidth=1.5)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSE Loss")
    ax.set_title("MLP Training Loss Curve")
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    plt.savefig("outputs/mlp_loss_curve.png", dpi=120)
    plt.close()
    print("  Saved: outputs/mlp_loss_curve.png")

    
    # 3. Extract penultimate-layer features
    
    print("\n")
    print("STEP 3: Extracting penultimate-layer features")
    print("\n")

    # Feature extractor for a single sample (row vector)
    # Normalise penultimate features for stable dot-product kernel
    Phi_all_tmp = mlp.penultimate_features(X_tr)
    phi_mean = np.mean(Phi_all_tmp, axis=0)
    phi_std = np.std(Phi_all_tmp, axis=0) + 1e-8

    def feature_extractor(x):
        raw = mlp.penultimate_features(x.reshape(1, -1)).ravel()
        return (raw - phi_mean) / phi_std

    # Features for all training data
    Phi_tr = mlp.penultimate_features(X_tr)   # (n_tr, 64)
    Phi_te = mlp.penultimate_features(X_te)
    Phi_svr_tr = mlp.penultimate_features(X_svr_tr)
    Phi_svr_te = mlp.penultimate_features(X_svr_te)

    print(f"Penultimate feature shape (train): {Phi_tr.shape}")

   
    # 4. t-SNE visualisation
    
    print("\n")
    print("STEP 4: t-SNE visualisation of NN features")
    print("\n")

    # Sub-sample 500 points for t-SNE speed
    idx_tsne = np.random.choice(Phi_tr.shape[0], min(500, Phi_tr.shape[0]), replace=False)
    Phi_tsne = Phi_tr[idx_tsne]
    y_tsne = y_tr[idx_tsne]

    # Normalize features before t-SNE
    Phi_tsne_norm, _, _ = normalize(Phi_tsne)

    print("  Running t-SNE (n=500, 500 iterations) ...")
    tsne = TSNE(n_components=2, perplexity=30, lr=200, n_iter=500)
    Y_tsne = tsne.fit_transform(Phi_tsne_norm)

    fig, ax = plt.subplots(figsize=(8, 6))
    sc = ax.scatter(Y_tsne[:, 0], Y_tsne[:, 1], c=y_tsne,
                    cmap="plasma", s=15, alpha=0.8)
    plt.colorbar(sc, ax=ax, label="mess_duration_min (normalised)")
    ax.set_title("t-SNE of NN Penultimate Features\n(colour = target value)", fontsize=13)
    ax.set_xlabel("t-SNE 1")
    ax.set_ylabel("t-SNE 2")
    plt.tight_layout()
    plt.savefig("outputs/tsne_nn_features.png", dpi=120)
    plt.close()
    print("  Saved: outputs/tsne_nn_features.png")

   
    # 5 & 6. Train all Kernel SVRs and compare
    
    print("\n")
    print("STEP 5 & 6: Training Kernel SVRs and comparison")
    print("\n")

    results = {}

    # Common SVR hyper-params
    C = 1.0
    eps = 0.1
    lr_svr = 0.5    # will be clamped by safe_lr inside KernelSVR
    max_iter_svr = 2000

    #  (a) Linear kernel 
    print("\n[1/7] Linear Kernel SVR")
    svr_lin = KernelSVR(kernel_fn=linear_kernel, C=C, epsilon=eps,
                        max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_lin.fit(X_svr_tr, y_svr_tr)
    r2_lin = svr_lin.score(X_svr_te, y_svr_te)
    rmse_lin = svr_lin.rmse(X_svr_te, y_svr_te)
    results["Linear"] = dict(r2=r2_lin, rmse=rmse_lin, model=svr_lin,
                             kfn="linear", params={})
    print(f"  Linear SVR  Test R²={r2_lin:.4f}  RMSE={rmse_lin:.4f}")

    # (b) Polynomial d=2 
    print("\n[2/7] Polynomial Kernel (d=2) SVR")
    kfn_p2 = lambda xi, xj: polynomial_kernel(xi, xj, c=1.0, d=2)
    svr_p2 = KernelSVR(kernel_fn=kfn_p2, C=C, epsilon=eps,
                       max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_p2.fit(X_svr_tr, y_svr_tr)
    r2_p2 = svr_p2.score(X_svr_te, y_svr_te)
    rmse_p2 = svr_p2.rmse(X_svr_te, y_svr_te)
    results["Poly(d=2)"] = dict(r2=r2_p2, rmse=rmse_p2, model=svr_p2,
                                kfn="poly", params={"d": 2})
    print(f"  Poly(d=2)  Test R²={r2_p2:.4f}  RMSE={rmse_p2:.4f}")

    # (c) Polynomial d=3 
    print("\n[3/7] Polynomial Kernel (d=3) SVR")
    kfn_p3 = lambda xi, xj: polynomial_kernel(xi, xj, c=1.0, d=3)
    svr_p3 = KernelSVR(kernel_fn=kfn_p3, C=C, epsilon=eps,
                       max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_p3.fit(X_svr_tr, y_svr_tr)
    r2_p3 = svr_p3.score(X_svr_te, y_svr_te)
    rmse_p3 = svr_p3.rmse(X_svr_te, y_svr_te)
    results["Poly(d=3)"] = dict(r2=r2_p3, rmse=rmse_p3, model=svr_p3,
                                kfn="poly", params={"d": 3})
    print(f"  Poly(d=3)  Test R²={r2_p3:.4f}  RMSE={rmse_p3:.4f}")

    # (d) RBF gamma=0.01
    print("\n[4/7] RBF Kernel (γ=0.01) SVR")
    kfn_r1 = lambda xi, xj: rbf_kernel(xi, xj, gamma=0.01)
    svr_r1 = KernelSVR(kernel_fn=kfn_r1, C=C, epsilon=eps,
                       max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_r1.fit(X_svr_tr, y_svr_tr)
    r2_r1 = svr_r1.score(X_svr_te, y_svr_te)
    rmse_r1 = svr_r1.rmse(X_svr_te, y_svr_te)
    results["RBF(γ=0.01)"] = dict(r2=r2_r1, rmse=rmse_r1, model=svr_r1,
                                  kfn="rbf", params={"gamma": 0.01})
    print(f"  RBF(γ=0.01)  Test R²={r2_r1:.4f}  RMSE={rmse_r1:.4f}")

    #(e) RBF gamma=0.1 
    print("\n[5/7] RBF Kernel (γ=0.1) SVR")
    kfn_r2 = lambda xi, xj: rbf_kernel(xi, xj, gamma=0.1)
    svr_r2 = KernelSVR(kernel_fn=kfn_r2, C=C, epsilon=eps,
                       max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_r2.fit(X_svr_tr, y_svr_tr)
    r2_r2 = svr_r2.score(X_svr_te, y_svr_te)
    rmse_r2 = svr_r2.rmse(X_svr_te, y_svr_te)
    results["RBF(γ=0.1)"] = dict(r2=r2_r2, rmse=rmse_r2, model=svr_r2,
                                 kfn="rbf", params={"gamma": 0.1})
    print(f"  RBF(γ=0.1)  Test R²={r2_r2:.4f}  RMSE={rmse_r2:.4f}")

    # (f) RBF gamma=1.0 
    print("\n[6/7] RBF Kernel (γ=1.0) SVR")
    kfn_r3 = lambda xi, xj: rbf_kernel(xi, xj, gamma=1.0)
    svr_r3 = KernelSVR(kernel_fn=kfn_r3, C=C, epsilon=eps,
                       max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_r3.fit(X_svr_tr, y_svr_tr)
    r2_r3 = svr_r3.score(X_svr_te, y_svr_te)
    rmse_r3 = svr_r3.rmse(X_svr_te, y_svr_te)
    results["RBF(γ=1.0)"] = dict(r2=r2_r3, rmse=rmse_r3, model=svr_r3,
                                 kfn="rbf", params={"gamma": 1.0})
    print(f"  RBF(γ=1.0)  Test R²={r2_r3:.4f}  RMSE={rmse_r3:.4f}")

    #  (g) Neural kernel 
    print("\n[7/7] Neural Kernel SVR")
    kfn_nn = lambda xi, xj: neural_kernel(xi, xj, feature_extractor)
    svr_nn = KernelSVR(kernel_fn=kfn_nn, C=C, epsilon=eps,
                       max_iter=max_iter_svr, tol=1e-4, lr=lr_svr)
    svr_nn.fit(X_svr_tr, y_svr_tr)
    r2_nn = svr_nn.score(X_svr_te, y_svr_te)
    rmse_nn = svr_nn.rmse(X_svr_te, y_svr_te)
    results["Neural"] = dict(r2=r2_nn, rmse=rmse_nn, model=svr_nn,
                             kfn="neural", params={})
    print(f"  Neural SVR  Test R²={r2_nn:.4f}  RMSE={rmse_nn:.4f}")

 
    # 7. Comparison bar chart
    print("\n")
    print("STEP 7: Comparison plots")
    print("\n")

    kernel_names = list(results.keys())
    r2_vals = [results[k]["r2"] for k in kernel_names]
    rmse_vals = [results[k]["rmse"] for k in kernel_names]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    colors = plt.cm.tab10(np.linspace(0, 0.7, len(kernel_names)))

    axes[0].bar(kernel_names, r2_vals, color=colors)
    axes[0].set_title("Test R² by Kernel", fontsize=13)
    axes[0].set_ylabel("R²")
    axes[0].set_ylim([min(0, min(r2_vals)) - 0.05, max(r2_vals) + 0.05])
    axes[0].tick_params(axis="x", rotation=30)
    for i, v in enumerate(r2_vals):
        axes[0].text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=9)

    axes[1].bar(kernel_names, rmse_vals, color=colors)
    axes[1].set_title("Test RMSE by Kernel", fontsize=13)
    axes[1].set_ylabel("RMSE (normalised units)")
    axes[1].tick_params(axis="x", rotation=30)
    for i, v in enumerate(rmse_vals):
        axes[1].text(i, v + 0.002, f"{v:.3f}", ha="center", fontsize=9)

    plt.tight_layout()
    plt.savefig("outputs/kernel_comparison.png", dpi=120)
    plt.close()
    print("  Saved: outputs/kernel_comparison.png")

    # Print comparison table
    print("\n  ┌─────────────────┬───────────┬───────────┐")
    print("  │ Kernel          │  Test R²  │ Test RMSE │")
    print("  ├─────────────────┼───────────┼───────────┤")
    for k in kernel_names:
        print(f"  │ {k:<15}  │  {results[k]['r2']:>7.4f}  │  {results[k]['rmse']:>7.4f}  │")
    print("  └─────────────────┴───────────┴───────────┘")


    print("\n")
    print("STEP 8: Kernel matrix visualisations")
    print("\n")

    idx_km = np.random.choice(X_svr_tr.shape[0], min(200, X_svr_tr.shape[0]), replace=False)
    Xkm = X_svr_tr[idx_km]
    Phi_km = Phi_svr_tr[idx_km]

    K_lin = linear_kernel_matrix(Xkm)
    K_p2 = poly_kernel_matrix(Xkm, c=1.0, d=2)
    K_p3 = poly_kernel_matrix(Xkm, c=1.0, d=3)
    K_r1 = rbf_kernel_matrix(Xkm, gamma=0.01)
    K_r2 = rbf_kernel_matrix(Xkm, gamma=0.1)
    K_r3 = rbf_kernel_matrix(Xkm, gamma=1.0)
    K_nn = neural_kernel_matrix(Xkm, feature_extractor)

    matrices = {
        "Linear": K_lin,
        "Poly (d=2)": K_p2,
        "Poly (d=3)": K_p3,
        "RBF γ=0.01": K_r1,
        "RBF γ=0.1": K_r2,
        "RBF γ=1.0": K_r3,
        "Neural": K_nn,
    }

    fig, axes = plt.subplots(2, 4, figsize=(20, 9))
    axes = axes.ravel()
    for idx_p, (name, Km) in enumerate(matrices.items()):
        im = axes[idx_p].imshow(Km, aspect="auto", cmap="viridis")
        axes[idx_p].set_title(f"Kernel Matrix: {name}", fontsize=11)
        axes[idx_p].set_xlabel("Sample")
        axes[idx_p].set_ylabel("Sample")
        plt.colorbar(im, ax=axes[idx_p])
    # hide last unused subplot
    axes[-1].set_visible(False)
    plt.suptitle("Kernel Matrix Heat-maps (200 training samples)", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig("outputs/kernel_matrices.png", dpi=100, bbox_inches="tight")
    plt.close()
    print("  Saved: outputs/kernel_matrices.png")

     
    print("STEP 9: Decision boundary plots (2D PCA)")
    print("\n")

    X2d_tr = pca_project(X_svr_tr, n_components=2)
    X2d_te = pca_project(X_svr_te, n_components=2)

    fig, axes = plt.subplots(2, 4, figsize=(22, 10))
    axes = axes.ravel()

    kernel_pred_pairs = [
        ("Linear", results["Linear"]["model"]),
        ("Poly(d=2)", results["Poly(d=2)"]["model"]),
        ("Poly(d=3)", results["Poly(d=3)"]["model"]),
        ("RBF(γ=0.01)", results["RBF(γ=0.01)"]["model"]),
        ("RBF(γ=0.1)", results["RBF(γ=0.1)"]["model"]),
        ("RBF(γ=1.0)", results["RBF(γ=1.0)"]["model"]),
        ("Neural", results["Neural"]["model"]),
    ]

    for idx_p, (name, model) in enumerate(kernel_pred_pairs):
        y_pred_te = model.predict(X_svr_te)
        sc = axes[idx_p].scatter(X2d_te[:, 0], X2d_te[:, 1],
                                 c=y_pred_te, cmap="plasma", s=20, alpha=0.8)
        axes[idx_p].set_title(f"{name}\nR²={results[name]['r2']:.3f}  RMSE={results[name]['rmse']:.3f}",
                              fontsize=10)
        axes[idx_p].set_xlabel("PC 1")
        axes[idx_p].set_ylabel("PC 2")
        plt.colorbar(sc, ax=axes[idx_p])

    # True values in last panel
    sc = axes[-1].scatter(X2d_te[:, 0], X2d_te[:, 1],
                          c=y_svr_te, cmap="plasma", s=20, alpha=0.8)
    axes[-1].set_title("True target\n(2D PCA)", fontsize=10)
    axes[-1].set_xlabel("PC 1")
    axes[-1].set_ylabel("PC 2")
    plt.colorbar(sc, ax=axes[-1])

    plt.suptitle("SVR Predictions in 2D PCA Space (test set)", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig("outputs/decision_boundaries_2d.png", dpi=100, bbox_inches="tight")
    plt.close()
    print("  Saved: outputs/decision_boundaries_2d.png")

    print("\n")
    print("STEP 10: Summary figure")
    print("\n")

    fig = plt.figure(figsize=(16, 5))
    gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.35)

    # Panel 1: MLP loss
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(loss_history, color="steelblue", linewidth=1.5)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("MSE Loss")
    ax1.set_title("MLP Training Loss")
    ax1.grid(True, alpha=0.4)

    # Panel 2: R² comparison
    ax2 = fig.add_subplot(gs[1])
    ax2.barh(kernel_names[::-1], [results[k]["r2"] for k in kernel_names[::-1]],
             color=plt.cm.tab10(np.linspace(0, 0.7, len(kernel_names))))
    ax2.set_xlabel("Test R²")
    ax2.set_title("Kernel SVR – Test R²")
    ax2.axvline(0, color="gray", linewidth=0.8)

    # Panel 3: RMSE comparison
    ax3 = fig.add_subplot(gs[2])
    ax3.barh(kernel_names[::-1], [results[k]["rmse"] for k in kernel_names[::-1]],
             color=plt.cm.tab10(np.linspace(0, 0.7, len(kernel_names))))
    ax3.set_xlabel("Test RMSE")
    ax3.set_title("Kernel SVR – Test RMSE")

    plt.suptitle("Section 7: Neural Network Features for Kernel Methods", fontsize=14)
    plt.savefig("outputs/summary.png", dpi=120, bbox_inches="tight")
    plt.close()
    print("  Saved: outputs/summary.png")

    print("\n")
    print("ALL DONE.  Outputs written to ./outputs/")
    print("\n")


if __name__ == "__main__":
    main()