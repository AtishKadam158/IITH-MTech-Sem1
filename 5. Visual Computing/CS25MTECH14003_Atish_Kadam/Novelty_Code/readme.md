# AFL — Analytic Federated Learning with SVD Compression

> **One-round, gradient-free federated learning** with closed-form aggregation, automatic regularisation, and rank-*r* communication compression.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Novelty Contributions](#2-novelty-contributions)
3. [File Directory Structure](#3-file-directory-structure)
4. [Environment & Dependencies](#4-environment--dependencies)
5. [Google Colab — Quick Start](#5-google-colab--quick-start)
6. [Argument Reference](#6-argument-reference)
7. [Experiment Commands](#7-experiment-commands)
   - [CIFAR-10 Experiments](#71-cifar-10-experiments)
   - [CIFAR-100 Experiments](#72-cifar-100-experiments)
   - [Tiny-ImageNet Experiments](#73-tiny-imagenet-experiments)
   - [Scalability (Large K) Experiments](#74-scalability-large-k-experiments)
8. [Understanding the Output](#8-understanding-the-output)
9. [Communication Cost Analysis](#9-communication-cost-analysis)
10. [Reproducibility Notes](#10-reproducibility-notes)

---

## 1. Problem Statement

Federated Learning (FL) trains a shared model across many distributed clients without transferring raw data — preserving privacy. Classical gradient-based FL (e.g., FedAvg) requires many communication rounds and can diverge under non-IID data distributions, where each client holds only a subset of the total class labels.

**Analytic Federated Learning (AFL)** addresses these issues by replacing iterative gradient descent with a single-round, closed-form least-squares solution. Each client computes two statistics from its local data — a feature correlation matrix and a label correlation matrix — and sends them to the server for exact aggregation via the Woodbury matrix identity.

### Core challenges this codebase tackles

| Challenge | Where it appears | How AFL addresses it |
|---|---|---|
| Non-IID data (heterogeneous label distributions) | Clients hold few or skewed classes | Dirichlet / PAT partitioning; analytic solution is exact regardless of distribution |
| Numerical instability at low data regimes | Rank-deficient covariance matrices | Auto-regularisation guard (`rg=0` path in `afl_.py`) |
| High communication cost for large feature spaces | Sending full weight matrices | Rank-*r* SVD compression (novel contribution) |
| Regularisation bias in the global model | Ridge penalty shifts the solution | Optional `--clean_reg` post-processing step |
| Scalability to many clients (K = 500 / 1000) | Sequential Woodbury merging | Memory-efficient GPU ↔ CPU tensor management |

---

## 2. Novelty Contributions

This codebase introduces **three novel additions** on top of the base AFL framework:

### Novelty 1 — Automatic Regularisation Guard

**File:** `afl_.py` → `local_update()`

When `--rg 0` is passed (default), the covariance matrix `X^T X` is frequently rank-deficient in non-IID federated settings (clients with very few samples per class). A direct matrix inversion would be numerically undefined or produce garbage values.

**Contribution:** Instead of failing silently, the code falls back to a *data-driven ridge* value:

```
rg_auto = max(trace(X^T X) / (d × 1000), 1e-6)
```

This keeps the system stable without requiring the user to hand-tune a regularisation coefficient for every experimental configuration.

### Novelty 2 — Rank-*r* SVD Compression of Local Weight Matrices

**File:** `afl_.py` → `local_update()` and `compute_comm_cost()`

Each client's local weight matrix `W ∈ ℝ^{feat × classes}` is normally transmitted in full. For large feature spaces (ResNet-18: 512 dims) and many classes (CIFAR-100: 100, TinyImageNet: 200), this dominates communication overhead.

**Contribution:** Before transmission, `W` is factored via truncated SVD:

```
W ≈ U_r  ·  diag(S_r)  ·  Vh_r
```

where `r ≪ min(feat, classes)`. Only the three factor matrices are "transmitted" (their sizes are tracked for cost accounting), and `W` is reconstructed at the server. Savings are measured and reported at the end of every run.

**Transmitted bytes (per client):**

| Without compression | With rank-r |
|---|---|
| `feat × classes × 8` bytes | `(feat·r + r + r·classes) × 8` bytes |

### Novelty 3 — Communication Cost Analysis & Reporting

**File:** `afl_.py` → `compute_comm_cost()` / `print_comm_cost_report()`

A full breakdown of communication overhead is computed and printed after every run, comparing original vs. compressed transmission size, showing per-client and total costs, and explaining why savings may be low when the `C` matrix (covariance) dominates.

---

## 3. File Directory Structure

```
Novelty_Code/
│
├── main.py              # Entry point — argument parsing, training loop, evaluation, CSV logging
├── afl_.py              # Core AFL logic: local update, aggregation, regularisation cleaning,
│                        #   SVD compression, communication cost analysis
├── dataset.py           # Data loading (CIFAR-10/100, TinyImageNet), Dirichlet/PAT partitioning
├── resnet.py            # ResNet backbone definitions (18 / 34 / 50 / 101 / 152)
│                        #   — fc layer removed; outputs 512-d feature vectors
│
└── README.md            # This file
```

> **Note:** Data is downloaded automatically on first run into `./data/` (CIFAR-10/100) or must be placed manually for TinyImageNet (see Section 5).

**Output files generated at runtime:**

```
{dataset}_{arch}_{num_clients}_{alpha}.csv   # Auto-appended results log per experiment
```

---

## 4. Environment & Dependencies

### Python version

Python **3.8 or higher** is required (tested on 3.10).

### Core packages

| Package | Purpose |
|---|---|
| `torch >= 2.0` | Tensor ops, GPU acceleration, `torch.linalg` (SVD / inverse) |
| `torchvision >= 0.15` | Dataset classes, ResNet pretrained weights, transforms |
| `numpy` | Array utilities, random seed control |
| `scikit-learn` | `train_test_split` (used in dataset partitioning) |
| `ujson` | Fast JSON for dataset config files |

### Install

```bash
pip install torch torchvision numpy scikit-learn ujson
```

On Google Colab only `ujson` needs to be installed manually — everything else is pre-installed:

```bash
!pip install ujson
```

### Hardware

| Setting | Minimum | Recommended |
|---|---|---|
| GPU | Any CUDA GPU | T4 (Colab free tier works) |
| VRAM | ~4 GB | 16 GB for K=1000 |
| RAM | 8 GB | 16 GB |

All heavy matrix operations (SVD, inversion) happen on GPU; tensors are moved to CPU between client iterations to manage VRAM.

---

## 5. Google Colab — Quick Start

### Step 1 — Open a GPU runtime

`Runtime → Change runtime type → T4 GPU`

### Step 2 — Upload your code files

```python
from google.colab import files
uploaded = files.upload()   # Select: main.py, afl_.py, dataset.py, resnet.py
```

### Step 3 — Install the missing dependency

```bash
!pip install ujson
```

### Step 4 — (TinyImageNet only) Download and set up the dataset

TinyImageNet is not available via torchvision and must be fetched manually:

```bash
!wget http://cs231n.stanford.edu/tiny-imagenet-200.zip
!unzip -q tiny-imagenet-200.zip -d data/
```

The expected directory tree is:

```
data/
└── tiny-imagenet-200/
    ├── train/
    │   ├── n01443537/
    │   │   └── images/  *.JPEG
    │   └── ...
    └── val/
        └── images/  *.JPEG   ← flat, needs restructuring (see below)
```

> **Important:** TinyImageNet's `val/` folder ships with a flat layout. Run the following to restructure it into class sub-folders (required by `ImageFolder`):
>
> ```python
> import os, shutil, pandas as pd
> val_dir = "data/tiny-imagenet-200/val"
> df = pd.read_csv(f"{val_dir}/val_annotations.txt", sep="\t",
>                  header=None, names=["file","class","x","y","w","h"])
> for _, row in df.iterrows():
>     dest = f"{val_dir}/{row['class']}"
>     os.makedirs(dest, exist_ok=True)
>     shutil.move(f"{val_dir}/images/{row['file']}", f"{dest}/{row['file']}")
> ```

### Step 5 — Run an experiment

```bash
!python main.py \
  --dataset cifar100 \
  --num_clients 100 \
  --niid \
  --partition dir \
  --alpha 0.1 \
  --rg 1 \
  --clean_reg \
  --rank_r 32 \
  --pretrained \
  --gpu 0
```

### Step 6 — Download results CSV

```python
from google.colab import files
files.download("cifar100_resnet18_100_0.1.csv")
```

---

## 6. Argument Reference

### Dataset & Architecture

| Argument | Default | Description |
|---|---|---|
| `--dataset` | `cifar100` | Dataset: `cifar10`, `cifar100`, `tinyimagenet` |
| `-a / --arch` | `resnet18` | Backbone architecture |
| `--pretrained` | `False` | Use ImageNet pre-trained weights |
| `--batch-size` | `512` | Batch size for feature extraction |
| `--gpu` | `0` | GPU device index |

### Federated Learning

| Argument | Default | Description |
|---|---|---|
| `--num_clients` | `50` | Number of federated clients (K) |
| `--niid` | `False` | Enable non-IID data partitioning |
| `--partition` | `dir` | Partition strategy: `dir` (Dirichlet) or `pat` (pathological) |
| `--alpha` | `0.1` | Dirichlet concentration parameter (lower = more heterogeneous) |
| `--balance` | `False` | Enforce balanced sample counts across clients |
| `--shred` | `10` | Minimum samples per class per client |

### Regularisation

| Argument | Default | Description |
|---|---|---|
| `--rg` | `0` | Ridge coefficient. `0` enables auto-regularisation |
| `--clean_reg` | `False` | Remove ridge bias post-aggregation (requires `--rg > 0`) |

### SVD Compression (Novelty)

| Argument | Default | Description |
|---|---|---|
| `--rank_r` | `0` | Rank for SVD compression of W. `0` = disabled |

### Seeds & Paths

| Argument | Default | Description |
|---|---|---|
| `--seed` | `1` | NumPy seed (data partitioning) |
| `--modelseed` | `1` | PyTorch seed (model init) |
| `--data` | `./data` | Root directory for datasets |
| `--datadir` | `./dataset` | Directory for partition config files |

---

## 7. Experiment Commands

All experiments use 100 clients, non-IID Dirichlet partitioning, pretrained ResNet-18, `rg=1`, `clean_reg`, and `rank_r=32` unless noted.

---

### 7.1 CIFAR-10 Experiments

**Effect of Dirichlet heterogeneity (alpha)**

```bash
# alpha = 0.1  (standard heterogeneity)
!python main.py \
  --dataset cifar10 --num_clients 100 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# alpha = 0.05  (higher heterogeneity)
!python main.py \
  --dataset cifar10 --num_clients 100 --niid \
  --partition dir --alpha 0.05 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

**Effect of minimum samples per class (shred / S)**

```bash
# S = 4
!python main.py \
  --dataset cifar10 --num_clients 100 --niid \
  --partition dir --alpha 0.1 --shred 4 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# S = 2
!python main.py \
  --dataset cifar10 --num_clients 100 --niid \
  --partition dir --alpha 0.1 --shred 2 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

---

### 7.2 CIFAR-100 Experiments

**Effect of Dirichlet heterogeneity (alpha)**

```bash
# alpha = 0.1
!python main.py \
  --dataset cifar100 --num_clients 100 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# alpha = 0.05
!python main.py \
  --dataset cifar100 --num_clients 100 --niid \
  --partition dir --alpha 0.05 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

**Effect of minimum samples per class (shred / S)**

```bash
# S = 10  (default)
!python main.py \
  --dataset cifar100 --num_clients 100 --niid \
  --partition dir --alpha 0.1 --shred 10 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# S = 5
!python main.py \
  --dataset cifar100 --num_clients 100 --niid \
  --partition dir --alpha 0.1 --shred 5 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

---

### 7.3 Tiny-ImageNet Experiments

**Effect of Dirichlet heterogeneity (alpha)**

```bash
# alpha = 0.1
!python main.py \
  --dataset tinyimagenet --num_clients 100 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# alpha = 0.05
!python main.py \
  --dataset tinyimagenet --num_clients 100 --niid \
  --partition dir --alpha 0.05 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

**Effect of minimum samples per class (shred / S)**

```bash
# S = 10
!python main.py \
  --dataset tinyimagenet --num_clients 100 --niid \
  --partition dir --alpha 0.1 --shred 10 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# S = 5
!python main.py \
  --dataset tinyimagenet --num_clients 100 --niid \
  --partition dir --alpha 0.1 --shred 5 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

---

### 7.4 Scalability (Large K) Experiments

These experiments test AFL's behaviour with significantly more clients.

**CIFAR-100 — large client counts**

```bash
# K = 500
!python main.py \
  --dataset cifar100 --num_clients 500 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# K = 1000
!python main.py \
  --dataset cifar100 --num_clients 1000 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

**Tiny-ImageNet — large client counts**

```bash
# K = 500
!python main.py \
  --dataset tinyimagenet --num_clients 500 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0

# K = 1000
!python main.py \
  --dataset tinyimagenet --num_clients 1000 --niid \
  --partition dir --alpha 0.1 \
  --rg 1 --clean_reg --rank_r 32 --pretrained --gpu 0
```

---

## 8. Understanding the Output

Each run prints the following sections to stdout:

```
Dataset: cifar100  |  num_classes: 100
=> using pre-trained model 'resnet18'

Training locally!
Client 0 Train Acc: 87.42%
Client 1 Train Acc: 91.03%
...

Local training time: 42.17s

Aggregating!
Aggregation done!

================================================================
  COMMUNICATION COST REPORT
================================================================
  ...

Evaluating global model!
Total time (train + agg): 49.83s
Global Accuracy: 74.21%

Cleaning regularization...
Accuracy after cleaning: 75.08%
Total time (with cleaning): 50.11s

Saved results to cifar100_resnet18_100_0.1.csv
```

**CSV columns (one row per run):**

```
[local_train_acc_list]  |  -  |  global_acc  |  cleaned_acc  |  -
|  local_time  |  total_time  |  cleaning_time  |  -
|  orig_total_MB  |  comp_total_MB  |  saving_MB  |  saving_pct  |  rank_r
|  -  |  args
```

---

## 9. Communication Cost Analysis

The communication report is printed after every run. Example interpretation:

```
================================================================
  COMMUNICATION COST REPORT
================================================================
  Embedding size (feat)   : 512
  Num classes             : 100
  Num clients (K)         : 100
  Rank-r compression      : 32 (effective = 32)
  C matrix dominance      : 97.0% of total per-client cost
----------------------------------------------------------------
                                   Original   Compressed
----------------------------------------------------------------
  W matrix  (per client)          0.0391MB    0.0137MB
  C matrix  (per client)          2.0000MB    2.0000MB
  Total     (per client)          2.0391MB    2.0137MB
----------------------------------------------------------------
  TOTAL     (all clients)        203.910MB  201.370MB
  W-only savings                      64.9%
  Overall savings                      1.2%  (2.540 MB saved)
================================================================
```

**Key insight:** On CIFAR-10/100 with ResNet-18, the covariance matrix `C ∈ ℝ^{512×512}` dominates (97%+ of bandwidth). SVD compression only targets `W`, so overall savings are small. On larger datasets (more classes, larger backbones), or when `C` compression is added, savings become substantial — the report explains this automatically.

---

## 10. Reproducibility Notes

- Seeds are fixed via `--seed` (data partition) and `--modelseed` (model). Both default to `1`.
- `cudnn.deterministic = True` and `cudnn.benchmark = False` are set automatically.
- All experiments in the notebook use **pretrained ResNet-18** (`--pretrained`). Without pretrained weights, accuracy will be significantly lower since AFL does not fine-tune the backbone.
- The `--clean_reg` flag has **no effect** when `--rg 0`. A warning is printed when this combination is used.
- When `--rg 0`, the auto-regularisation value varies per client and per run depending on data. For fully deterministic results across machines, pass an explicit `--rg 1`.

---

## Citation / Related Work

This codebase implements and extends:

- **AFL (Analytic Federated Learning):** Closed-form federated learning via recursive Woodbury aggregation.
- **Rank-r communication compression:** Novel SVD-based compression of per-client weight matrices prior to aggregation (original contribution of this work).
- **Auto-regularisation:** Data-driven ridge fallback for numerically stable inversion under non-IID conditions (original contribution of this work).