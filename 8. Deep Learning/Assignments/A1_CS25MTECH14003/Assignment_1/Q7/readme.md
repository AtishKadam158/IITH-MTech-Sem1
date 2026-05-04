## Setup & Run

```bash
pip install numpy matplotlib
python experiments.py
```

> Place `iith_campus_life_5000.csv` in the same folder before running.

---

## Folder Structure

```
Q7/
├── kernels.py
├── experiments.py
├── iith_campus_life_5000.csv
└── outputs/
```

---

## What's Implemented

- **MLP** (from scratch) — architecture `[13 → 256 → 128 → 64 → 1]`, ReLU, mini-batch SGD
- **Penultimate features** — `φ_NN(x) = h^(L-1)(x)` via `MLP.penultimate_features()`
- **t-SNE** (from scratch) — visualises 64-dim NN features
- **Kernels** — Linear, Polynomial (d=2,3), RBF (γ=0.01, 0.1, 1.0), Neural
- **KernelSVR** (from scratch) — projected sub-gradient dual solver

---

## Outputs

| File | Description |
|---|---|
| `mlp_loss_curve.png` | Training loss curve |
| `tsne_nn_features.png` | t-SNE of NN features |
| `kernel_comparison.png` | R² and RMSE bar charts |
| `kernel_matrices.png` | Kernel matrix heat-maps |
| `decision_boundaries_2d.png` | Predictions in 2D PCA space |