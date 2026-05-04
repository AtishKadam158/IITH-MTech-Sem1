# Task 6 — MLP from Scratch (NumPy only)

## Setup
```bash
pip install numpy matplotlib
```

## Files
```
activations.py   — activation functions + derivatives
losses.py        — MSE, BCE, hinge losses + derivatives
optimizers.py    — SGD, Momentum, Nesterov, AdaGrad, RMSProp, Adam, Muon
mlp.py           — MLP class (forward, backward, fit, predict)
data_utils.py    — data loading, preprocessing, PCA
run_task6.py     — experiment runner (sections 6.3–6.7)
iith_campus_life_5000.csv
```

## Run
```bash
python run_task6.py
```
Plots saved to `outputs_task6/`.

## Quick Usage
```python
from mlp import MLP
from data_utils import prepare
from pathlib import Path

d = prepare(Path("iith_campus_life_5000.csv"))

model = MLP(
    layer_sizes=[21, 64, 64, 1],
    activations=["relu", "relu", "sigmoid"],
    loss="cross_entropy",
    optimizer="adam",
    learning_rate=0.01,
)
model.fit(d.X_train, d.y_train, d.X_val, d.y_val, epochs=100)
print(model.evaluate(d.X_test, d.y_test))
```

## Experiments
| Section | Description |
|---|---|
| 6.3.1 | Depth ablation — 1 to 4 hidden layers |
| 6.3.2 | Width ablation — widths 8 to 256 |
| 6.3.3 | Activation comparison — sigmoid / tanh / ReLU / leaky ReLU |
| 6.4 | Loss comparison — BCE, MSE, hinge |
| 6.5 | Optimizer comparison + LR sensitivity |
| 6.6 | L1 / L2 regularization sweep |
| 6.7 | PCA feature visualization + MLP vs Adaline |

## Notes
- Labels for `hinge` loss must be in {−1, +1}
- Early stopping restores best val checkpoint automatically
- 21 input features (one-hot + numeric), binary classification target